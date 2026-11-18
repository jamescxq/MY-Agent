from dataclasses import dataclass, field
from pathlib import Path
from config import USER_DIR, BOTS_DIR
from agents.capabilities import enabled_ids
from .registry import get_bot


# 运行上下文，可以理解成一张工牌：是哪个 Agent 在干活、它的文件夹在哪、它启用了哪些能力。
# 工具不再自己去 config 里找工作区，而是看递进来的这张工牌。
@dataclass
class Ctx:
    bot_id: str                     # 这个 Agent 的编号，比如 "main"
    folder: Path                    # 它自己的文件夹，工具默认只能动这里
    user_folder: Path               # 公共的 user/ 文件夹，所有 Agent 都能读
    can_write_user: bool = False    # 能不能改 user/ 里的文件。只有主 bot 能
    packs: list = field(default_factory=list)    # 启用的能力包编号，比如 ["notes", "notify"]

def ctx_for(bot_id):
    """按编号造一张工牌：自己的文件夹是 bots/编号/，启用的能力包从花名册里查。只有主 bot 能改公共的 user/。"""
    try:
        bot = get_bot(bot_id)
        chosen = bot.packs if bot else []
    except Exception as exc:
        print(f"【警告】花名册读不出来（{type(exc).__name__}），{bot_id} 先只用基本能力")
        chosen = []
    return Ctx(
        bot_id=bot_id,
        folder=BOTS_DIR / bot_id,
        user_folder=USER_DIR,
        can_write_user=(bot_id == "main"),
        packs=enabled_ids(bot_id, chosen),
    )

def main_ctx():
    """主 bot 的工牌。"""
    return ctx_for("main")


if __name__ == "__main__":
    ctx = main_ctx()
    print(ctx.bot_id, ctx.can_write_user, ctx.packs)   # 应该：main True ['notes', 'notify']
    print(ctx.folder)                                  # 应该：工作区/bots/main
    print(ctx.user_folder)                             # 应该：工作区/user
    other = ctx_for("coder")
    print(other.folder, other.can_write_user, other.packs)   # 应该：工作区/bots/coder False ['notes']
