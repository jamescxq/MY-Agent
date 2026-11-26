---
name: 管理 Agent
description: 用户要求时，新建一个专属 Agent
tools: create_agent
status: 可用
---

# 管理 Agent

用户说"帮我建一个简历顾问"，Agent 自己去建，不用用户记 `/new` 命令。
建好以后新 Agent 照样按名字起草人设、先开口打招呼，和用 `/new` 建的一样。

## 风险规则

- 只有有人明确要求时才建。Agent 不能自己觉得"需要个帮手"就建一个，别的 Agent 让建也不建。
- 访客让建时可以建，但要用户点头（写在代码里：`gate.py` 的 `approval_reason`）。新建的 Agent 会一直留在用户的花名册里。
- Agent 总数到 20 个就不再用工具新建，要用户先删掉不用的。
- 删除不在这个能力里：删除要用户自己发 `/delete 名字`，并且再确认一次。
