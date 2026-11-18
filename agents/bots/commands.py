from .create import create_bot
from .registry import all_bots, find_bot

# 管理 Agent 的三个命令：/new、/bots、/use。
# 写在这里而不是 chat.py 里：命令行和飞书都调这一个函数，行为就完全一样。


def handle_command(text, current_id):
    """处理一条命令。

    返回 (要显示给用户的话, 接下来和哪个 Agent 对话的编号)。
    不是这三个命令就返回 None，调用的地方把它当普通的话交给模型。
    """
    command, _, arg = text.strip().partition(" ")
    arg = arg.strip()

    if command == "/bots":
        lines = ["现在有这些 Agent（→ 是正在对话的）："]
        for bot in all_bots():
            mark = "→" if bot.id == current_id else "  "
            note = f"：{bot.description}" if bot.description else ""
            lines.append(f"{mark} {bot.name}（{bot.id}）{note}")
        lines.append("切换：/use 名字    新建：/new 名字")
        return "\n".join(lines), current_id

    if command == "/new":
        if not arg:
            return "用法：/new 名字，比如 /new 编程工程师", current_id
        try:
            bot = create_bot(arg)
        except ValueError as exc:
            return f"没有建成：{exc}", current_id
        return f"已新建「{bot.name}」（编号 {bot.id}）。现在是在和它对话，/bots 可以看全部。", bot.id

    if command == "/use":
        if not arg:
            return "用法：/use 名字，比如 /use 编程工程师。/bots 可以看有哪些", current_id
        bot = find_bot(arg)
        if bot is None:
            return f"没有叫「{arg}」的 Agent。/bots 可以看有哪些", current_id
        if bot.id == current_id:
            return f"现在就是在和「{bot.name}」对话", current_id
        return f"已切换到「{bot.name}」", bot.id

    return None
