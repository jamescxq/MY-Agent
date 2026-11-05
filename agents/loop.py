import anthropic
from config import MODEL
from agents.tools import TOOL_FUNCTIONS

client = anthropic.Anthropic(
    max_retries=2,
    timeout=60.0,
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
        result["content"] = TOOL_FUNCTIONS[block.name](**block.input)
    except FileNotFoundError:
        result["content"] = f"抱歉，我没找到文件，你看看是不是文件路径错了"
        result["is_error"] = True
    except PermissionError:
        result["content"] = f"抱歉，我没有使用这个文件的权限，需要你亲自操作"
        result["is_error"] = True
    except UnicodeError:
        result["content"] = f"抱歉，这个文件编码我不懂，我目前只能处理UTF-8 文本"
        result["is_error"] = True
    except (TypeError, ValueError):
        result["content"] = "抱歉，工具参数或数据不正确，你可以检查参数名称、类型和值。"
        result["is_error"] = True
    except Exception as exc:
        print(f"这个工具{block.name}坏了！: {type(exc).__name__}")
        result["content"] = "我的工具坏了，需要维修！！！"
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
