from agents.capabilities import load_packs, enabled_ids
from .create import create_bot
from .registry import all_bots, get_bot, find_bot, save_packs

# 管理 Agent 的命令：/new、/bots、/use、/packs。
# 写在这里而不是 chat.py 里：命令行和飞书都调这一个函数，行为就完全一样。

MAIN = "main"


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
        lines.append("切换：/use 名字    新建：/new 名字    看能力：/packs")
        return "\n".join(lines), current_id, False

    if command == "/new":
        if not arg:
            return "用法：/new 名字，比如 /new 编程工程师", current_id, False
        try:
            bot = create_bot(arg)
        except ValueError as exc:
            return f"没有建成：{exc}", current_id, False
        return f"已新建「{bot.name}」（编号 {bot.id}）。现在是在和它对话，/bots 可以看全部。", bot.id, False

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
