from dataclasses import dataclass
from pathlib import Path


# 运行上下文，可以理解成一张工牌：是哪个 Agent 在干活、它的文件夹在哪。
# 工具不再自己去 config 里找工作区，而是看递进来的这张工牌。
@dataclass
class Ctx:
    bot_id: str          # 这个 Agent 的编号，比如 "main"
    folder: Path         # 它自己的文件夹
    user_folder: Path    # 公共的 user/ 文件夹，所有 Agent 都能看


if __name__ == "__main__":
    from config import WORKSPACE

    ctx = Ctx(bot_id="main", folder=WORKSPACE, user_folder=WORKSPACE)
    print(ctx.bot_id)      # 应该：main
    print(ctx.folder)      # 应该：工作区的路径
