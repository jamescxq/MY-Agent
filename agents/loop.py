import time
import anthropic
from config import MODEL
from agents.tools import TOOL_FUNCTIONS
from agents.permission import approval_reason, ask_user
from agents.permission.taint import has_outside
from agents.audit import write_audit, write_trace, check_limit
from agents.models import vendor

client = anthropic.Anthropic(
    max_retries=2,
    timeout=300.0,
)
MAX_STEPS = 10
OUT_OF_STEPS = "（步数用完了，停下来了）"     # 转满 MAX_STEPS 圈还没做完时，run_agent 返回这句话
WORKER_MARK = "·子智能体"                    # 用量记录里，子智能体的调用记在"派它的 Agent 的编号 + 这几个字"名下
CACHE ={"type": "ephemeral"}       # 提示词缓存的标记：存 5 分钟，5 分钟内又用到就重新计时


def call_model(bot, step, **request):
    """调一次模型，顺手记一行用量。所有调模型的地方都走这里，这样不会有哪次漏记。

    bot、step 只用来记账：谁调的、第几步。request 是原样交给模型的那些参数（system、messages……）。
    调之前先看今天的用量到没到上限，到了就抛出 OverLimit，不调（见 agents/audit/budget.py）。
    """
    check_limit()
    start = time.time()
    try:
        response = client.messages.create(model=MODEL, **request)
    except anthropic.APIStatusError as exc:
        # 接口明确拒绝了这次请求：把它给的原因打在终端里再往上报。只看错误的名字查不出原因
        print(f"【系统】模型接口拒绝了这次请求（{exc.status_code}）：{str(exc)[:400]}")
        raise
    seconds = time.time() - start
    usage = response.usage
    read = getattr(usage, "cache_read_input_tokens", 0) or 0          # 从缓存里读的
    write = getattr(usage, "cache_creation_input_tokens", 0) or 0     # 这一次新存进缓存的
    sent = usage.input_tokens + read + write        # 接口报的 input_tokens 只是"没走缓存的那部分"，三个加起来才是一共发了多少
    write_trace(bot, step, sent, usage.output_tokens, seconds, read, write)
    print("【调试】发了", sent, "个 token（其中", read, "个从缓存读，", write, "个新存进缓存），回了", usage.output_tokens, "个，用了", round(seconds, 2), "秒")
    return response


def cache_marks(system):
    """给请求加上"提示词缓存"的标记，返回要放进请求里的那几项。

    每次调模型都要把工具清单、提示词、整段对话重发一遍。加了标记以后，接口那边会把"和上次一模一样的开头"
    存起来，下次只按很低的价钱算。标记有两个：
      1. 加在提示词的最后：工具清单和提示词是固定的那一大段，存一次，之后每次调用都能读到。
      2. 写在请求的最外层：接口自己把它放在对话的最后，对话变长它跟着往后挪。
         这样用工具时的第二次调用，能读到第一次调用发过的全部内容。
    只要开头有一个字不一样（工具换了、提示词改了），从那里往后就都读不到缓存，要重新存。

    这家接口不认这个标记（见 agents/models/），或者提示词是空的，就不加。
    """
    if not system or not vendor().CACHE_MARKS:
        return {"system": system}
    return {
        "system": [{"type": "text", "text": system, "cache_control": CACHE}],
        "cache_control": CACHE,
    }


def note_server_tools(response):
    """服务器那边替我们执行的工具（搜索、读网页）不经过 execute_tool，没法事前记审计，
    只能事后记：回复里写着它搜了什么、读了哪个网址。"""
    for block in response.content:
        if block.type != "server_tool_use":
            continue
        asked = block.input if isinstance(block.input, dict) else {}
        write_audit(block.name, asked.get("url") or asked.get("query"), "服务器执行", True)


def execute_tool(ctx, block, allowed, approver, outside=False):
    """执行模型要用的一个工具，先过几道关。outside=True 表示这段对话里读过外面的内容（网页、搜索结果）。"""
    result = {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": "",
        "is_error": False,
    }
    approval = "不需要"
    if block.name not in allowed or block.name not in TOOL_FUNCTIONS:
        result["content"] = f"抱歉，我还没有接入这个{block.name}工具"
        result["is_error"] = True
        write_audit(block.name, block.input.get("path"), approval, False)
        return result
    try:
        reason = approval_reason(ctx, block.name, block.input, outside)     # 不用问就是空的
        if reason:
            approval = "同意" if approver(block.name, block.input, reason) else "拒绝"
        if approval == "拒绝":
            result["content"] = "用户拒绝了这个操作。不要重试，先问用户怎么做"
            result["is_error"] = True
        else:
            result["content"] = TOOL_FUNCTIONS[block.name](ctx, **block.input)
    except Exception as exc:
        result["content"] = f"工具 {block.name} 出错（{type(exc).__name__}）：{exc}。请换个办法，或告诉用户。"
        result["is_error"] = True
    write_audit(block.name, block.input.get("path"), approval, not result["is_error"])
    return result

def run_agent(ctx, system, tools, messages, approver=ask_user):
    """让一个 Agent 处理 messages 里最新的那句话：转圈调模型、用工具，直到它说完。返回它最后说的话。

    注意：一段对话从头到尾，tools 和 system 都不能变。模型的回复里带着思考记录（thinking 块），
    接口规定它只能在"产生它时的那份工具清单和提示词"下发回去，变了就拒绝整个请求（400）。
    以前访客说话时会从清单里拿掉几个工具，就撞上了这一条，经过记在 docs/bugs/ 里。
    以后要给某个人开关能力，做法是让这个会话重新开始（像 /packs 那样），不要中途改清单。
    """
    who = ctx.bot_id + WORKER_MARK if ctx.worker else ctx.bot_id      # 记用量时写谁：子智能体的单独记，好看出派单花了多少
    for step in range(MAX_STEPS):
        response = call_model(
            who, step + 1,
            max_tokens=4096,
            tools=tools,
            messages=messages,
            **cache_marks(system),          # system 在这里面，带着缓存标记
        )
        print("【调试】第", step + 1, "次调用，stop_reason:", response.stop_reason)
        has_tool = any(block.type == "tool_use" for block in response.content)
        has_text = any(block.type == "text" for block in response.content)
        if response.stop_reason == "max_tokens" and (has_tool or not has_text):
            return "（回复被截断，这次没有执行。可以让我分几次写。）"
        messages.append({"role": "assistant","content": response.content})
        note_server_tools(response)

        if response.stop_reason == "pause_turn":
            # 服务器那边搜到一半先停下了。什么都不用加，把对话原样再发一次，它会接着做（算一步，受 MAX_STEPS 限制）
            continue
        if response.stop_reason != "tool_use":
            reply = ''
            for block in response.content:
                if block.type == 'text':
                    reply+= block.text
            return reply

        allowed = [t["name"] for t in tools]
        outside = has_outside(messages)     # 这段对话里读过外面的内容吗？读过的话，写操作要先问用户
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print("【调试】调用工具:", block.name)
            result = execute_tool(ctx, block, allowed, approver, outside)
            results.append(result)
        messages.append({"role": "user", "content": results})

    return OUT_OF_STEPS
