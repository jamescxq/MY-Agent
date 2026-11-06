# MY-Agent 设计计划

> 一个有自己名字和性格、记得主人、会用工具、每天自己整理记忆，
> 能在网页和飞书里聊天，并且能把活儿分给多个子 Agent 并行去做的私人助手。

参考资料：CowAgent 源码、DeepSeek《Super-agent 设计探索》、OpenAI Agents SDK 文档、Claude Code 子 Agent 文档、腾讯混元 Hyra 2.0（只公开了思路，编排代码没开源）、Pi Durable（TypeScript 实验库，只学思路不安装）。

---

## 1. 总体架构

```
  网页说话     飞书消息     定时提醒     厨师干完活
      │           │           │           │
      └───────────┴─────┬─────┴───────────┘
                        ▼
              ┌──────────────────┐
              │    事件队列       │  所有输入都变成"事件"排队
              └──────────────────┘
                        │  代码先过滤（Fast Path）
                        ▼
              ┌──────────────────┐
              │   前台 Router     │  小模型，快、便宜
              │   闲聊直接回      │  只有轻量工具
              │   要干活就派单    │  积压的事件一次批处理
              └──────────────────┘
                 │ 派单         ▲ 汇报（也是一个事件）
                 ▼              │
       ┌────────────┐  ┌────────────┐
       │ 厨师：通用  │  │ 厨师：查资料 │  同一份循环代码 + 不同模板
       │ 全部工具    │  │ 只读工具    │  大模型，后台运行
       └────────────┘  └────────────┘
                 │
                 ▼
         workspace（项目外，不进 GitHub）
         ├─ AGENT.md / USER.md             档案
         ├─ MEMORY.md                      长期记忆，每晚"做梦"整理
         ├─ memory/YYYY-MM-DD.md           每日记录
         └─ skills/*/SKILL.md              小牛自己写的 skill
```

一句话：**接待的人不干活，干活的人不接待。**

- 主循环、前台、每个厨师，跑的都是同一个 `run_agent()`，只是配置不同。
- 所有输入（用户消息、飞书消息、定时提醒、厨师汇报）都是事件，进同一个队列。

### 文件放在哪

**代码一样，记忆不同。** 大家共用同一份代码，每个人的 Agent 有自己的记忆，所以表现不一样。

| 位置 | 放什么 | 谁来改 | 传 GitHub |
|---|---|---|---|
| `MY-Agent/`（项目） | 代码、`docs/`、`requirements.txt`、`.env.example` | 开发者 | 传 |
| `MY-Agent/templates/` | `RULE.md`（直接读取）；`AGENT.md`、`USER.md`、`MEMORY.md`、`BOOTSTRAP.md`（空白模板）；`agents/*.md`（厨师模板） | 开发者 | 传 |
| `MY-Agent-workspace/`（项目外） | 自己的 `AGENT.md`、`USER.md`、`MEMORY.md`，以及运行时产生的文件 | Agent 自己 | 不传 |
| `MY-Agent/.env` | Key、`MODEL`、`ANTHROPIC_BASE_URL` | 每个人自己 | 不传 |

- `RULE.md` 是公告栏，放在 `templates/`，只进提示词，Agent 读不到也改不了这个文件。
- 第一次运行时，`ensure_workspace()` 把空白模板复制到工作空间，已有的文件不覆盖。
- 换服务商不改代码：Anthropic SDK 自己读 Key 和 `ANTHROPIC_BASE_URL`，`config.py` 读 `MODEL`。只支持有 Anthropic 兼容接口的服务商；遇到不兼容的再照 CowAgent 写翻译层。
- GitHub 只推 `main`。本地的 `old-history` 分支含有旧的个人档案，**绝不推送，也不用 `git push --all`**。

---

## 2. 采用的设计

### ✅ 要做，并且现在就把位置留好

| 优点 | 来自 | 我们怎么做 |
|---|---|---|
| 一份循环代码 + 不同配置 | CowAgent、Claude、OpenAI | 工具循环写成函数 `run_agent(配置, 任务)`，而不是写死在 `chat.py` 里。已完成，最重要 |
| 前台不干活 | Super-agent | 前台的工具里没有读写文件、执行命令，只有"派单"和"回复" |
| 闲聊前台直接回 | 解决"链路太慢"的问题 | "你好"、"谢谢"这种不派单，前台直接回。只有真正要干活才派单，避免每句话都多走一圈 |
| 前台小模型，厨师大模型 | Super-agent、Claude Code | `config.py` 里分开配 `ROUTER_MODEL` 和 `WORKER_MODEL` |
| 厨师模板写成 md 文件 | Claude Code、CowAgent | `templates/agents/*.md`，开头写 name、description、tools、model，正文是提示词。加一种厨师，只要加一个文件 |
| 厨师只返回总结，但要带证据 | Claude Code、CowAgent、Hyra 2.0 | 中间过程不回传，避免撑爆前台的上下文。总结里必须附上证据（改了哪个文件、命令输出、结果），不能只说"做完了" |
| 派单要写完整任务说明 | CowAgent 的 `_build_brief` | 派单工具强制要求填"任务"和"背景"两个参数 |
| 用工具派单，不用转交 | OpenAI 的 `as_tool` | 前台始终掌控对话，用户永远只跟前台说话。OpenAI 的 `handoffs` 转交方式不用 |
| 危险工具黑名单 + 数量限制 | CowAgent | 厨师不能发消息、不能建定时任务、不能再开厨师；最多同时 3 个；步数有上限 |
| 审批门 | 我们自己的改造计划 | 危险操作先问用户，并且避开 CowAgent 的反斜杠漏洞 |
| 凭据永远不进上下文 | Super-agent 8.4 | 工具需要 key 时，由代码从 `.env` 读，绝不放进提示词或工具结果 |
| 工具分三类来源 | CowAgent、Anthropic | 动自己的文件、记忆、核心能力（派单）的**自己写**；上网搜索、读网页用 **Anthropic 服务端工具**；飞书、GitHub 等外部服务**接 MCP**。总数控制在几十个以内 |
| Skill 按需加载 | Claude Code、CowAgent | `workspace/skills/<名字>/SKILL.md`，开头写 name、description。提示词里只放名字和一句话说明，要用时再 `read_file` 读全文，skill 再多也不撑爆提示词 |
| Agent 自己写 skill | CowAgent 的 evolution | 做成一件事后，把经验写成新 skill，下次照做。这是"每日演化"的核心 |
| 经验分三级 | Hyra 2.0 的 Books | 第一次发现记为"观察"；重复验证过升为"已验证"；会改变小牛行为的"约定"（新规矩、新 skill）**必须用户确认**才生效 |
| 沙箱分两层 | CowAgent `policy.py` 自己承认"不是系统沙箱" | 第一层是代码检查（`ALLOWED`、路径判断），能被绕过，不算真沙箱。第二层是系统级隔离（Docker 容器）。**有 `bash` 之前，必须先有审批门，最好跑在容器里** |

### ⏳ 要做，但放到后面

| 优点 | 来自 | 为什么放后面 |
|---|---|---|
| 异步厨师 | Super-agent 4.1 | 要用到多线程，先做同步版（派单后等它做完），跑通再改成后台运行 |
| 两级过滤 | Super-agent 3.1 | 接入飞书、群里消息多了以后才真正需要 |
| 截断 + 续读入口 | Super-agent Inline & Spill、CowAgent | 工具结果太长就截断，告诉模型"需要的话再读"。做读文件工具时顺手加 |
| 链式召回 | Super-agent 3.3 | 记忆多了以后才需要。先做简单的 `MEMORY.md` |
| 追问直通厨师 | Super-agent 3.2 | 先简化：前台有一个"给某厨师补充消息"的工具，由前台转达。等接入飞书话题，再做自动直通 |
| 看门狗 | Super-agent 6 | 先用代码做：厨师超时、超步数就强制结束。用 LLM 做的看门狗以后再说 |
| 断点恢复（状态存数据库） | Super-agent 5.1、LangGraph 的 checkpointer、Pi Durable | 每次 `messages` 变化就存进 SQLite，重启后接着做。现在只是聊天，崩了重来不亏；厨师在后台跑长任务时就必须有。自己写，不用框架 |
| 中间层、独立复核 | Hyra 2.0 的 Mission 层、Review Worker | Mission 是"项目经理"，管一条跨好几天的长任务；Review Worker 用全新上下文从头复核结果。私人助手两层（前台 + 厨师）先够用，任务变长再加 |

### ❌ 不做

| 优点 | 为什么不做 |
|---|---|
| 投机执行：后台提前尝试 | 很费钱，个人助手用不上 |
| 前台水平切分、多前台 | 公司级别的规模才需要，Super-agent 文章自己也说他们的团队规模用一个前台就够了 |
| 上云、存算分离第二步 | 太重，等真的需要 24 小时在线再考虑 |
| fork 模式：子 Agent 继承全部对话 | 和"上下文隔离"冲突，容易又慢又贵 |
| A2A：跨组织 Agent 通信 | Super-agent 文章里也还是开放问题 |

---

## 3. 路线图

每个阶段都要能跑起来、看到效果，然后提交一次。

### ✅ 阶段 0：地基

- [x] 调通 Claude 调用（`playground/hello_claude.py`）
- [x] 多轮对话（`chat.py`）
- [x] 外部 md 提示词 + `agents/prompt/builder.py` 拼接
- [x] 目录结构、`config.py`
- [x] 第一个工具 `update_profile`

### ✅ 阶段 1：会用工具

- [x] 工具循环写成 `run_agent()`，`chat.py` 调用它
- [x] 说"叫你小牛"，它自己调用 `update_profile` 写进 `AGENT.md`
- [x] 初始化完成后删除 `BOOTSTRAP.md`，重启后直接认识用户
- [x] 工具登记处：多个工具统一管理
- [x] 加简单工具：`get_time`、`read_file`、`list_file`、`edit_file`
- [x] 工作空间搬到项目外，新增 `templates/`；代码上传 GitHub
- [x] `write_file`：替代 `update_profile`

对照 CowAgent：`agent/protocol/agent_stream.py` 的 `run_stream`

### ▶ 阶段 2：安全

- [x] 权限检查：只能动 workspace 里的文件，路径先规范化再判断（`agents/tools/guard.py`）
- [x] 审批门：危险操作先问 y/n（`agents/permission/gate.py`）
- [x] 最大步数、工具出错返回文字而不是崩溃
- [x] 凭据不进上下文：密钥只放 `.env`，工具不能访问 `.env` 开头的文件（`agents/tools/guard.py`）。拦不住聊天里粘贴的密钥，也拦不住写在其他文件里的密钥
- [x] 审计日志：每次工具调用记录时间、工具名、路径、是否审批、是否成功；只记摘要，不记完整正文和凭据，日志不放 C 盘（`agents/audit/audit.py`）。`success` 表示工具调用没有报错，不代表事情做成了
- [ ] 记住：代码检查不等于沙箱。没有审批门之前不加 `bash`；真要加，放进 Docker 容器里跑

对照 CowAgent：`agent/permission/policy.py`，以及反斜杠漏洞（`shlex` posix 模式吃掉反斜杠）

### 阶段 3：记忆 + 每日演化

- [ ] 每轮对话追加到 `memory/YYYY-MM-DD.md`
- [ ] `MEMORY.md` 拼进提示词
- [ ] 上下文太长时裁剪旧对话；工具结果截断 + 续读入口
- [ ] 工作空间单独 `git init` 做本地备份，不设远程、不推送
- [ ] "做梦"：每晚读当天记录，改写 `MEMORY.md`，自动提交到工作空间的本地 git
- [ ] Skill：`workspace/skills/*/SKILL.md`，builder 只拼名字和说明，用时再读全文
- [ ] 自己写 skill：做成一件事后把经验写成新 skill，先给用户看再保存
- [ ] 经验分级：`MEMORY.md` 里的经验标上"观察 / 已验证 / 约定"，做梦时升级；升为"约定"要用户点头

对照 CowAgent：`_trim_messages`、`summarizer.py` 的 Deep Dream、`agent/skills/`、`agent/evolution/`；对照 Hyra 2.0 的 Books

### 阶段 4：同步版前台 + 厨师

- [ ] `templates/agents/*.md` 厨师模板（先做"通用"和"查资料"两种）
- [ ] 派单工具：参数为 种类、任务、背景
- [ ] 厨师汇报格式：总结 + 证据（改动的文件、关键输出）
- [ ] 前台只有派单、回复等轻量工具；闲聊直接回
- [ ] `ROUTER_MODEL` / `WORKER_MODEL` 分开配置
- [ ] 黑名单、最多同时 3 个、步数上限

对照 CowAgent：`agent/subagent/templates.py`、`runner.py`

### 阶段 5：事件队列 + 异步厨师

- [ ] 所有输入变成事件，进同一个队列
- [ ] 派单后立即返回"已开始"，厨师在后台运行，干完把汇报作为事件放回队列
- [ ] 前台一次处理积压的多条事件（批处理）
- [ ] 代码看门狗：超时、超步数强制结束
- [ ] "给某厨师补充消息"工具

对照：Super-agent 第 2、3、4.1、6 节

### 阶段 6：网页界面

- [ ] FastAPI 后端 + 简单网页
- [ ] 流式输出
- [ ] 断点恢复：对话和厨师状态存进 SQLite，每次 `messages.append` 后保存，启动时读回来
  - 坑 1：Claude 的回复是 SDK 对象（ThinkingBlock、ToolUseBlock），要先转成普通字典再存，思考块的 signature 要原样保留
  - 坑 2：工具执行完、结果还没存就崩了，恢复后会再执行一遍。参考 Pi Durable 的做法：
    1. 执行前先存"我要做 X"，执行后再存"X 的结果"
    2. 恢复时看到只有前一笔：工具标了"重复执行没关系"（如改文件）就重跑；没标的（如发消息）不重跑，给模型回一个"上次被中断了"的 `tool_result`，让它自己决定
    3. 用户的审批答案也存起来，恢复后不再重复问
    4. 做不到"外部操作恰好只执行一次"，这是所有方案的共同限制

### 阶段 7：接入飞书

- [ ] 飞书机器人收发消息
- [ ] 两级过滤：代码先筛，LLM 再判断
- [ ] 同一话题的追问直通对应厨师
- [ ] 审批门走飞书：危险操作发卡片给用户点"同意 / 拒绝"（Hyra 2.0 用企业微信做同样的事）

### 以后再说

定时任务、微信或 X、MCP 外部工具、上云 24 小时在线、LLM 看门狗。

---

## 4. 原则

1. **每一步都能跑**：每次只加一样东西，跑通、提交，再加下一样。
2. **规则写在代码里，不只写在提示词里**：提示词是建议，代码才是保证。
3. **安全优先**：key 只放 `.env`；个人档案只放项目外的 workspace，绝不进 GitHub；危险操作必须经过用户同意。
4. **能用代码就不用 LLM**：LLM 调用是整条链路里最慢、最贵的部分。
5. **对照 CowAgent 学**：每完成一个阶段，回去读 CowAgent 对应的源码，看看人家多考虑了什么。
