import anthropic

from agents.bots import main_ctx, ctx_for, get_bot, handle_command, opening_for, take_newcomers, OPENING_NOTE
from agents.prompt.builder import build_system_prompt, assemble_prompt, get_agent_name
from agents.loop import run_agent
from agents.audit import OverLimit
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
print("输入 /bots 看有哪些 Agent，/new 名字 新建一个，/use 名字 切换，/delete 名字 删除，/packs 看能力。")

# 开场指令：不是 None 的时候，这一轮不等用户输入，由 Agent 先开口。
# 主 bot 第一次启动时就是这样（首次引导）；新建或切到一个没说过话的 Agent 时也是。
opening = opening_for(ctx)

while True:
    if opening is not None:
        user_input = ""
    else:
        try:
            user_input = input("你：")
        # EOFError：输入流结束，没有输入可以继续读。
        # KeyboardInterrupt：你按了Ctrl + C，主动中断程序。
        except (EOFError, KeyboardInterrupt):
            print("\n已退出，拜拜👋。")
            break

    # not user_input 表示“输入是空字符串”。
    if opening is None and not user_input.strip():
        continue

    if user_input == "/exit":
        break

    # /new、/bots、/use、/packs 由 agents/bots 处理；别的话返回 None，照常交给模型
    result = handle_command(user_input, ctx.bot_id) if opening is None else None
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
            if not messages:
                opening = opening_for(ctx)      # 一句话都没说过的 Agent：让它先打招呼
        for gone in [key for key in parked if get_bot(key) is None]:
            del parked[gone]                # 被删掉的 Agent，存着的对话也丢掉
        if opening is None:
            continue

    # 斜杠开头、但哪个命令都不是（多半是打错了）：直接提示，不交给模型
    if result is None and user_input.startswith("/") and user_input != "/retry":
        print("没有这个命令。输入 /bots 可以看有哪些 Agent 和能用的命令。")
        continue

    if opening is not None:
        # 代码替用户发一条开场指令，它的回答就是招呼。往下走的是和普通对话同一条路
        last_input = OPENING_NOTE
        messages.append({"role": "user", "content": opening})
        opening = None
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

    except OverLimit as exc:
        print(f"【系统】{exc}")       # 今天的用量到上限了：这一句没有调模型
        pending_retry = True
    else:
        pending_retry = False
        print(f"{get_agent_name(ctx)}：", reply)
        write_daily(ctx, last_input, reply)
        # 这一轮里它用工具新建了别的 Agent（你说"帮我建一个……"）：提醒一下怎么找到新来的
        for bot_id in take_newcomers():
            name = get_bot(bot_id).name
            print(f"【系统】「{name}」建好了。输入 /use {name} 和它对话，它会先打招呼。")
        backup_workspace("对话后自动备份")
    if pending_retry:
        print("对话还在，输入 /retry 可以重试。")
