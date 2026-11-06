import anthropic

from agents.prompt.builder import build_system_prompt, get_agent_name
from agents.loop import run_agent
from agents.tools import TOOLS

messages = []
system_prompt = build_system_prompt()

# 是否存在因接口异常而中断的请求
pending_retry = False

print("输入 /retry 重试中断的请求，输入 /exit 退出。")

while True:
    try:
        user_input = input("你：")
    # EOFError：输入流结束，没有输入可以继续读。
    # KeyboardInterrupt：你按了Ctrl + C，主动中断程序。
    except (EOFError, KeyboardInterrupt):
        print("\n已退出，拜拜👋。")
        break

    # not user_input 表示“输入是空字符串”。
    if not user_input.strip():
        continue

    if user_input == "/exit":
        break

    if user_input == "/retry":
        if not pending_retry:
            print("我觉得目前没有需要重试的请求哦。")
            continue

    # 重试时使用现有历史，不重复追加用户消息
    else:
        messages.append({
            "role": "user",
            "content": user_input,
        })
    try:
        system_prompt = build_system_prompt()
        reply = run_agent(system_prompt, TOOLS, messages)

    except anthropic.APIConnectionError:
        print("我链接不到这个api，你看看是不是网卡了")
        pending_retry = True

    except anthropic.APIStatusError as exc:
        reasons = {
            400: "请求不合法，参数不对。",
            401: "身份验证失败，请检查 API Key。",
            403: "没有权限使用该服务或模型。",
            404: "请求的资源不存在，请检查模型名称和接口地址。",
            422: "请求参数无法处理，请检查参数。",
            429: "请求受到限流，请稍后再试。",
        }
        reason = reasons.get(
            exc.status_code,
            "模型服务返回错误，请检查服务状态。",
        )
        print(f"【系统】HTTP {exc.status_code}：{reason}")
        pending_retry = True

    except anthropic.APIError as exc:
        print(f"【系统】模型接口异常：{type(exc).__name__}")
        pending_retry = True
    else:
        pending_retry = False
        print(f"{get_agent_name()}：", reply)
    if pending_retry:
            print(
                "我已经记住了这次的对话了。"
            )
