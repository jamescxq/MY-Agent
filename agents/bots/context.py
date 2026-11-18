from dataclasses import dataclass
from pathlib import Path
from config import USER_DIR, BOTS_DIR


# 运行上下文，可以理解成一张工牌：是哪个 Agent 在干活、它的文件夹在哪。
# 工具不再自己去 config 里找工作区，而是看递进来的这张工牌。
@dataclass
class Ctx:
    bot_id: str                     # 这个 Agent 的编号，比如 "main"
    folder: Path                    # 它自己的文件夹，工具默认只能动这里
    user_folder: Path               # 公共的 user/ 文件夹，所有 Agent 都能读
    can_write_user: bool = False    # 能不能改 user/ 里的文件。只有主 bot 能

def main_ctx():
    """主 bot 的工牌：自己的文件夹是 bots/main/，并且能改公共的 user/。"""
    return Ctx(bot_id="main", folder=BOTS_DIR / "main", user_folder=USER_DIR, can_write_user=True)


if __name__ == "__main__":
    ctx = main_ctx()
    print(ctx.bot_id)           # 应该：main
    print(ctx.folder)           # 应该：工作区/bots/main
    print(ctx.user_folder)      # 应该：工作区/user
