# 新 Agent 先开口：第一次和它对话时，由它先打招呼、介绍自己，不让用户进去以后没人说话。
#
# 做法：代码替用户发一条"开场指令"（OPENING）当作第一句话，它的回答就是招呼。
# 命令行、飞书、以后的网页，用的都是这一条，所以从哪里建，它说的都是同一种开场白。

from agents.prompt.texts import prompt_text

# 新 Agent 的开场指令。原文在 templates/prompts/opening.md
OPENING = prompt_text("opening")

# 主 bot 第一次启动时的开场指令。具体怎么引导写在 BOOTSTRAP.md 里（它已经在提示词里了），
# 这里只是让它先开口，并且把"选能力"这一步带上。原文在 templates/prompts/opening_main.md
MAIN_OPENING = prompt_text("opening_main")

OPENING_NOTE = "（刚新建，它先开口）"      # 每日记录里代替上面那一大段

MAIN = "main"


def is_fresh(ctx):
    """这个专属 Agent 是不是一句话都还没说过：它的文件夹里还没有每日记录（memory/）。主 bot 不算。"""
    return ctx.bot_id != MAIN and not (ctx.folder / "memory").exists()


def opening_for(ctx):
    """现在该不该让这个 Agent 先开口。该的话返回要发给它的开场指令，不该返回 None。

    - 说过话的（已经有每日记录）：不用。
    - 专属 Agent 还没说过话：用 OPENING。
    - 主 bot 第一次启动（首次引导 BOOTSTRAP.md 还在）：用 MAIN_OPENING。
    """
    if (ctx.folder / "memory").exists():
        return None
    if ctx.bot_id == MAIN:
        return MAIN_OPENING if (ctx.folder / "BOOTSTRAP.md").exists() else None
    return OPENING
