import anthropic
from config import MODEL
from agents.tools import UPDATE_PROFILE_TOOL, TOOL_FUNCTIONS

client = anthropic.Anthropic()
MAX_STEPS = 10

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
            if block.name in allowed:
                output = TOOL_FUNCTIONS[block.name](**block.input)
            else:
                output = f"拒绝:没有给你 {block.name} 这个工具"

            results.append({
                "type": "tool_result",
                "tool_use_id": block.id,
                "content": output,
            })
        messages.append({"role": "user", "content": results})

    return "（步数用完了，停下来了）"
