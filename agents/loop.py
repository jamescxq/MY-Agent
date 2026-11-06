import anthropic
from config import MODEL
from agents.tools import TOOL_FUNCTIONS
from agents.permission import need_approval, ask_user

client = anthropic.Anthropic(
    max_retries=2,
    timeout=300.0,
)
MAX_STEPS = 10
def execute_tool(block,allowed):
    result = {
        "type": "tool_result",
        "tool_use_id": block.id,
        "content": "",
        "is_error": False,
    }
    if block.name not in allowed or block.name not in TOOL_FUNCTIONS:
        result["content"] = f"抱歉，我还没有接入这个{block.name}工具"
        result["is_error"] = True
        return result
    try:
        if need_approval(block.name, block.input) and not ask_user(block.name, block.input):
            result["content"] = "用户拒绝了这个操作。不要重试，先问用户怎么做"
            result["is_error"] = True
        else:
            result["content"] = TOOL_FUNCTIONS[block.name](**block.input)
    except Exception as exc:
        result["content"] = f"工具 {block.name} 出错（{type(exc).__name__}）：{exc}。请换个办法，或告诉用户。"
        result["is_error"] = True
    return result

def run_agent(system, tools, messages):
    for step in range(MAX_STEPS):
        response = client.messages.create(
            model=MODEL,
            max_tokens=4096,
            system=system,
            tools=tools,
            messages=messages,
        )
        print("【调试】第", step + 1, "次调用，stop_reason:", response.stop_reason)
        print("【调试】这次发了多少 token:", response.usage.input_tokens)
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
            result = execute_tool(block,allowed)
            results.append(result)
        messages.append({"role": "user", "content": results})

    return "（步数用完了，停下来了）"
