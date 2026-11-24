import time
import anthropic
from config import MODEL
from agents.tools import TOOL_FUNCTIONS
from agents.permission import need_approval, ask_user, guest_blocked
from agents.audit import write_audit, write_trace

client = anthropic.Anthropic(
    max_retries=2,
    timeout=300.0,
)
MAX_STEPS = 10
def execute_tool(ctx, block, allowed, approver):
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
    if guest_blocked(ctx, block.name):
        result["content"] = "拒绝：现在是访客在说话，这个工具只有用户本人说话时才能用。不要重试，告诉访客这件事要用户本人来说"
        result["is_error"] = True
        write_audit(block.name, block.input.get("path"), "访客不能用", False)
        return result
    try:
        if need_approval(ctx, block.name, block.input):
            approval = "同意" if approver(block.name, block.input) else "拒绝"
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
    for step in range(MAX_STEPS):
        start = time.time()
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )
        seconds = time.time() - start
        # 每调一次模型记一行用量：谁调的、第几步、发了多少、回了多少、用了几秒
        write_trace(ctx.bot_id, step + 1, response.usage.input_tokens, response.usage.output_tokens, seconds)
        print("【调试】第", step + 1, "次调用，stop_reason:", response.stop_reason)
        print("【调试】发了", response.usage.input_tokens, "个 token，回了", response.usage.output_tokens, "个，用了", round(seconds, 2), "秒")
        has_tool = any(block.type == "tool_use" for block in response.content)
        has_text = any(block.type == "text" for block in response.content)
        if response.stop_reason == "max_tokens" and (has_tool or not has_text):
            return "（回复被截断，这次没有执行。可以让我分几次写。）"
        messages.append({"role": "assistant","content": response.content})

        if response.stop_reason != "tool_use":
            reply = ''
            for block in response.content:
                if block.type == 'text':
                    reply+= block.text
            return reply

        allowed = [t["name"] for t in tools]
        results = []
        for block in response.content:
            if block.type != "tool_use":
                continue
            print("【调试】调用工具:", block.name)
            result = execute_tool(ctx, block, allowed, approver)
            results.append(result)
        messages.append({"role": "user", "content": results})

    return "（步数用完了，停下来了）"
