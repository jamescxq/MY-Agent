import anthropic

from agents.bots import main_ctx, ctx_for, handle_command, is_fresh, OPENING, OPENING_NOTE
from agents.prompt.builder import build_system_prompt, assemble_prompt, get_agent_name
from agents.loop import run_agent
from agents.capabilities import tools_for
from agents.memory import write_daily, backup_workspace
from agents.context import trim_messages

messages = []
last_input = ""
ctx = main_ctx()      # 工牌：现在只有主 bot 一个
system_prompt = build_system_prompt(ctx)
tools = tools_for(ctx)      # 这个 Agent 能用的工具，按它启用的能力包算出来
backup_workspace("启动时备份")
# 是否存在因接口异常而中断的请求
pending_retry = False
# 切走的 Agent 先存在这里：编号 → (工牌, 提示词, 工具, 对话历史)，切回来时接着聊
parked = {}

def open_talk(bot_id):
    """切到一个 Agent：以前聊过就接着聊，没聊过就给它造工牌、拼提示词、开一段新对话。"""
    if bot_id in parked:
        return parked.pop(bot_id)
    new_ctx = ctx_for(bot_id)
    return new_ctx, assemble_prompt(new_ctx), tools_for(new_ctx), []

print("输入 /retry 重试中断的请求，输入 /exit 退出。")
print("输入 /bots 看有哪些 Agent，/new 名字 新建一个，/use 名字 切换，/packs 看能力。")

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

    # /new、/bots、/use、/packs 由 agents/bots 处理；别的话返回 None，照常交给模型
    result = handle_command(user_input, ctx.bot_id)
    greeting = False        # 这一轮是不是"新 Agent 先开口"
    if result is not None:
        text, bot_id, restart = result
        print(text)
        if restart:
            parked.pop(bot_id, None)        # 它的能力变了，旧对话不能接着用
        elif bot_id != ctx.bot_id:
            parked[ctx.bot_id] = (ctx, system_prompt, tools, messages)     # 把现在这个 Agent 的对话存起来
        if restart or bot_id != ctx.bot_id:
            ctx, system_prompt, tools, messages = open_talk(bot_id)
            pending_retry = False
            greeting = not messages and is_fresh(ctx)      # 一句话都没说过的 Agent：让它先打招呼
        if not greeting:
            continue

    if greeting:
        # 代码替用户发一条开场指令，它的回答就是招呼。往下走的是和普通对话同一条路
        last_input = OPENING_NOTE
        messages.append({"role": "user", "content": OPENING})
    elif user_input == "/retry":
        if not pending_retry:
            print("我觉得目前没有需要重试的请求哦。")
            continue

    # 重试时使用现有历史，不重复追加用户消息
    else:
        last_input = user_input
        messages.append({
            "role": "user",
            "content": user_input,
        })
    messages = trim_messages(messages)
    try:
        reply = run_agent(ctx, system_prompt, tools, messages)

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
        print(f"{get_agent_name(ctx)}：", reply)
        write_daily(ctx, last_input, reply)
        backup_workspace("对话后自动备份")
    if pending_retry:
        print("对话还在，输入 /retry 可以重试。")
