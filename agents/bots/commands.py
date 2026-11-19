from agents.capabilities import load_packs, enabled_ids
from config import feishu_app
from .create import create_bot
from .delete import delete_bot, file_count
from .persona import draft_persona
from .registry import all_bots, get_bot, find_bot, save_packs

# 管理 Agent 的命令：/new、/bots、/use、/packs、/delete，飞书里还有 /join、/leave。
# 写在这里而不是入口里：命令的逻辑只有一份。
#   handle_command()          给命令行用：一次只和一个 Agent 对话
#   handle_session_command()  给飞书用：一个会话里可以有多个 Agent

MAIN = "main"
CONFIRM = "确认"        # /delete 名字 后面跟上这个词，才真的删


def name_of(bot_id):
    bot = get_bot(bot_id)
    return bot.name if bot else bot_id


def created_text(bot):
    """新建成功以后告诉用户的话：建了什么，和它相关的能力现在是什么状态。

    能力只提醒、不替用户打开：要不要开由用户决定。
    """
    lines = [f"已新建「{bot.name}」（编号 {bot.id}）" + (f"：{bot.description}" if bot.description else "。")]
    packs = {pack.id: pack for pack in load_packs()}
    for pack_id in bot.suggested:
        pack = packs.get(pack_id)
        if pack is None:
            continue
        if pack.available:
            lines.append(f"和它相关的能力「{pack.name}」现在没开，想让它用就输入 /packs 打开。")
        else:
            lines.append(f"和它相关的能力「{pack.name}」还没接入，现在用不了。")
    return "\n".join(lines)


def delete_command(arg):
    """/delete 名字：只说明会删掉什么，不动手；/delete 名字 确认：真的删。

    返回 (要显示给用户的话, 被删掉的 Agent 的编号)。没删的时候编号是 None。
    分两步是因为删了它的人设和记忆就都不在了，要用户看清楚再点头。
    """
    if not arg:
        return "用法：/delete 名字。会先告诉你要删掉什么，你确认了才删", None
    name, confirmed = arg, False
    bot = find_bot(name)
    if bot is None and arg.endswith(" " + CONFIRM):
        name, confirmed = arg[:-len(CONFIRM)].strip(), True      # 去掉末尾的"确认"，前面才是名字
        bot = find_bot(name)
    if bot is None:
        return f"没有叫「{name}」的 Agent。/bots 可以看有哪些", None
    if bot.id == MAIN:
        return "主 Agent 不能删。", None
    if not confirmed:
        return (
            f"要删除「{bot.name}」（编号 {bot.id}）吗？\n"
            f"它的人设、记忆和每日记录（共 {file_count(bot.id)} 个文件）会搬进回收站，花名册和所有会话里都不再有它。\n"
            f"确认就发：/delete {bot.name} {CONFIRM}"
        ), None
    try:
        where = delete_bot(bot.id)
    except ValueError as exc:
        return f"没有删成：{exc}", None
    lines = [f"已删除「{bot.name}」。"]
    if where is not None:
        lines.append(f"它的文件搬到了工作区的回收站：{where.parent.name}/{where.name}，后悔了可以从那里拿回来。")
    if feishu_app(bot.id):
        key = bot.id.upper().replace("-", "_")
        lines.append(f".env 里 FEISHU_APP_ID_{key}、FEISHU_APP_SECRET_{key} 这两行已经没用了，可以自己删掉；飞书群里它的机器人也要你自己移出去。")
    return "\n".join(lines), bot.id


def handle_session_command(text, members):
    """处理一条命令。members 是这个会话的成员名单（Agent 编号的列表）。

    返回三样东西：(要显示给用户的话, 新的成员名单, 能力变了的 Agent 编号列表)。
    不是命令就返回 None，调用的地方把它当普通的话交给成员们。
    """
    command, _, arg = text.strip().partition(" ")
    arg = arg.strip()

    def roster(ids):
        return "、".join(name_of(bot_id) for bot_id in ids)

    if command == "/bots":
        lines = ["现在有这些 Agent（→ 是这个会话里的）："]
        for bot in all_bots():
            mark = "→" if bot.id in members else "  "
            note = f"：{bot.description}" if bot.description else ""
            lines.append(f"{mark} {bot.name}（{bot.id}）{note}")
        lines.append("让它加入：/join 名字    让它离开：/leave 名字    只留一个：/use 名字")
        lines.append("新建：/new 名字    删除：/delete 名字    看能力：/packs    让它们停下：/stop")
        return "\n".join(lines), members, []

    if command == "/new":
        if not arg:
            return "用法：/new 名字，比如 /new 编程工程师", members, []
        try:
            bot = create_bot(arg, draft=draft_persona)
        except ValueError as exc:
            return f"没有建成：{exc}", members, []
        joined = members + [bot.id]
        return f"{created_text(bot)}\n它加入了这个会话。现在的成员：{roster(joined)}。", joined, []

    if command in ("/join", "/leave", "/use"):
        if not arg:
            return f"用法：{command} 名字。/bots 可以看有哪些", members, []
        bot = find_bot(arg)
        if bot is None:
            return f"没有叫「{arg}」的 Agent。/bots 可以看有哪些", members, []
        if command == "/use":
            return f"这个会话现在只有「{bot.name}」。", [bot.id], []
        if command == "/join":
            if bot.id in members:
                return f"「{bot.name}」已经在这个会话里了。", members, []
            joined = members + [bot.id]
            return f"「{bot.name}」加入了这个会话。现在的成员：{roster(joined)}。话里叫谁的名字，就只有谁回答。", joined, []
        if bot.id not in members:
            return f"「{bot.name}」不在这个会话里。", members, []
        if len(members) == 1:
            return "这个会话只剩它一个了，不能再让它离开。想换人用 /use 名字", members, []
        left = [bot_id for bot_id in members if bot_id != bot.id]
        return f"「{bot.name}」离开了这个会话。现在的成员：{roster(left)}。", left, []

    if command == "/delete":
        reply, gone = delete_command(arg)
        if gone is None:
            return reply, members, []
        # 这个会话里只有它一个的话，删掉以后换回主 Agent。第三样写上它的编号：所有会话里和它的旧对话都作废
        left = [bot_id for bot_id in members if bot_id != gone] or [MAIN]
        return reply, left, [gone]

    if command == "/packs":
        if len(members) == 1:
            target, rest = members[0], arg
        else:
            # 多个成员时要写名字：/packs 二牛，或 /packs 二牛 2
            name, _, last = arg.rpartition(" ")
            bot = find_bot(arg)
            rest = ""
            if bot is None and name:
                bot, rest = find_bot(name), last
            if bot is None or bot.id not in members:
                return "这个会话里有多个 Agent，要写上名字：/packs 二牛 看它的能力，/packs 二牛 2 开关一项", members, []
            target = bot.id
        if not rest:
            return show_packs(target), members, []
        reply, _, changed = switch_pack(target, rest)
        return reply, members, [target] if changed else []

    return None


def handle_command(text, current_id):
    """处理一条命令。

    返回三样东西：(要显示给用户的话, 接下来和哪个 Agent 对话的编号, 这个 Agent 的对话要不要重新开始)。
    第三样是 True 的时候，说明它的能力变了，提示词和工具都要重新生成，旧的对话不能接着用。
    不是这几个命令就返回 None，调用的地方把它当普通的话交给模型。
    """
    command, _, arg = text.strip().partition(" ")
    arg = arg.strip()

    if command == "/bots":
        lines = ["现在有这些 Agent（→ 是正在对话的）："]
        for bot in all_bots():
            mark = "→" if bot.id == current_id else "  "
            note = f"：{bot.description}" if bot.description else ""
            lines.append(f"{mark} {bot.name}（{bot.id}）{note}")
        lines.append("切换：/use 名字    新建：/new 名字    删除：/delete 名字    看能力：/packs")
        return "\n".join(lines), current_id, False

    if command == "/new":
        if not arg:
            return "用法：/new 名字，比如 /new 编程工程师", current_id, False
        try:
            bot = create_bot(arg, draft=draft_persona)
        except ValueError as exc:
            return f"没有建成：{exc}", current_id, False
        return f"{created_text(bot)}\n现在是在和它对话，/bots 可以看全部。", bot.id, False

    if command == "/use":
        if not arg:
            return "用法：/use 名字，比如 /use 编程工程师。/bots 可以看有哪些", current_id, False
        bot = find_bot(arg)
        if bot is None:
            return f"没有叫「{arg}」的 Agent。/bots 可以看有哪些", current_id, False
        if bot.id == current_id:
            return f"现在就是在和「{bot.name}」对话", current_id, False
        return f"已切换到「{bot.name}」", bot.id, False

    if command == "/packs":
        if not arg:
            return show_packs(current_id), current_id, False
        return switch_pack(current_id, arg)

    if command == "/delete":
        reply, gone = delete_command(arg)
        if gone == current_id:              # 删掉的就是正在对话的这个：回到主 Agent
            return f"{reply}\n现在回到和「{name_of(MAIN)}」对话。", MAIN, False
        return reply, current_id, False

    if command in ("/join", "/leave"):
        return "命令行里一次只和一个 Agent 对话，用 /use 名字 切换。多个 Agent 一起聊要在飞书里。", current_id, False

    return None


def show_packs(bot_id):
    """列出全部能力包，以及正在对话的这个 Agent 开了哪些。"""
    bot = get_bot(bot_id)
    on = enabled_ids(bot_id, bot.packs if bot else [])
    lines = [f"「{bot.name if bot else bot_id}」的能力："]
    for number, pack in enumerate(load_packs(), start=1):
        if not pack.available:
            state = "还没接入"
        elif pack.always:
            state = "已启用（每个 Agent 都有）"
        elif pack.id in on:
            state = "已启用"
        else:
            state = "没启用"
        lines.append(f"  {number}. {pack.name}：{pack.description} —— {state}")
    lines.append("打开或关掉一项：/packs 序号，比如 /packs 2")
    return "\n".join(lines)


def switch_pack(bot_id, arg):
    """打开或关掉一个能力包。arg 是序号或名字。"""
    packs = load_packs()
    pack = None
    if arg.isdigit() and 1 <= int(arg) <= len(packs):
        pack = packs[int(arg) - 1]
    else:
        pack = next((p for p in packs if arg in (p.name, p.id)), None)
    if pack is None:
        return f"没有「{arg}」这一项。输入 /packs 看有哪些", bot_id, False
    if not pack.available:
        return f"「{pack.name}」还没接入，现在开不了", bot_id, False
    if pack.always:
        return f"「{pack.name}」每个 Agent 都有，不能关", bot_id, False
    if bot_id == MAIN:
        return "主 Agent 默认开着全部能用的能力，现在还不能单独关。可以新建一个 Agent 再给它选", bot_id, False

    bot = get_bot(bot_id)
    chosen = list(bot.packs)
    if pack.id in chosen:
        chosen.remove(pack.id)
        word = "关掉"
    else:
        chosen.append(pack.id)
        word = "打开"
    save_packs(bot_id, chosen)
    return f"已给「{bot.name}」{word}「{pack.name}」。它的能力变了，和它的对话重新开始。", bot_id, True
