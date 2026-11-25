import time
import anthropic
from config import MODEL
from agents.tools import TOOL_FUNCTIONS
from agents.permission import approval_reason, ask_user, guest_blocked
from agents.permission.taint import has_outside
from agents.audit import write_audit, write_trace

client = anthropic.Anthropic(
    max_retries=2,
    timeout=300.0,
)
MAX_STEPS = 10


def call_model(bot, step, **request):
    """调一次模型，顺手记一行用量。所有调模型的地方都走这里，这样不会有哪次漏记。

    bot、step 只用来记账：谁调的、第几步。request 是原样交给模型的那些参数（system、messages……）。
    """
    start = time.time()
    response = client.messages.create(model=MODEL, **request)
    seconds = time.time() - start
    write_trace(bot, step, response.usage.input_tokens, response.usage.output_tokens, seconds)
    print("【调试】发了", response.usage.input_tokens, "个 token，回了", response.usage.output_tokens, "个，用了", round(seconds, 2), "秒")
    return response


def is_server_tool(tool):
    """清单里的这一项，是不是"让模型那边的服务器去执行"的工具（比如 Claude 接口自带的搜索）。
    我们自己的工具都带着参数说明 input_schema，服务器那边的没有。"""
    return "input_schema" not in tool


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
    if guest_blocked(ctx, block.name, block.input):
        result["content"] = "拒绝：现在是访客在说话，这件事只有用户本人说话时才能做。不要重试，告诉访客这件事要用户本人来说"
        result["is_error"] = True
        write_audit(block.name, block.input.get("path"), "访客不能用", False)
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
    if ctx.guest:
        # 访客说话时，不给"服务器那边执行"的工具。它们不经过 execute_tool，那里的访客门禁拦不到，
        # 唯一能拦的地方就是这里：不放进清单，模型就用不了。
        tools = [tool for tool in tools if not is_server_tool(tool)]
    for step in range(MAX_STEPS):
        response = call_model(
            ctx.bot_id, step + 1,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
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

    return "（步数用完了，停下来了）"
