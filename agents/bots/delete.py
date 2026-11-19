from datetime import datetime
from config import STATE_DB, BOTS_DIR
from agents.store import remove_bot
from .registry import get_bot

# 删除一个专属 Agent。和 create.py 的 create_bot() 对着：所有入口删 Agent 都调这里的 delete_bot()。
#
# "删除"其实是搬走，不是真的抹掉：
#   - 它的文件夹（人设、记忆、每日记录）整个搬进工作区的回收站 trash/，名字是"编号__时间"。
#     后悔了可以从那里把文件拿回来。回收站在所有 Agent 的文件夹外面，工具碰不到。
#   - 花名册和所有会话的成员名单里去掉它。
# 删掉的编号以后不会再用（见 create.py 的 make_id）：.env 里按编号配的飞书应用不会套到别的 Agent 头上。

MAIN = "main"       # 主 bot 不能删
TRASH = "trash"     # 回收站的文件夹名，和 bots/ 并排


def trash_of(bots_dir):
    """回收站在哪：和 bots/ 并排的 trash/。"""
    return bots_dir.parent / TRASH


def trashed_ids(bots_dir):
    """回收站里有哪些编号。新建时要避开它们。"""
    trash = trash_of(bots_dir)
    if not trash.exists():
        return set()
    return {item.name.split("__")[0] for item in trash.iterdir()}


def file_count(bot_id, bots_dir=BOTS_DIR):
    """这个 Agent 的文件夹里一共有多少个文件。删之前告诉用户用。"""
    folder = bots_dir / bot_id
    if not folder.exists():
        return 0
    return sum(1 for item in folder.rglob("*") if item.is_file())


def delete_bot(bot_id, db=STATE_DB, bots_dir=BOTS_DIR):
    """删除一个 Agent。返回它的文件夹搬到了哪（它本来就没有文件夹的话返回 None）。

    删不了的时候抛出 ValueError，里面是给用户看的说明。
    要不要删由调用的地方先问用户，这个函数不问。
    """
    if bot_id == MAIN:
        raise ValueError("主 Agent 不能删")
    if get_bot(bot_id, db) is None:
        raise ValueError(f"花名册里没有编号是 {bot_id} 的 Agent")

    folder = bots_dir / bot_id
    target = None
    if folder.exists():
        trash = trash_of(bots_dir)
        trash.mkdir(parents=True, exist_ok=True)
        target = trash / f"{bot_id}__{datetime.now():%Y%m%d-%H%M%S}"
        try:
            folder.rename(target)               # 先搬文件夹：搬不走就什么都不动
        except OSError as exc:
            raise ValueError(f"它的文件夹搬不走（{exc.strerror or exc}）。可能里面有文件正被别的程序打开，关掉再试")
    try:
        remove_bot(bot_id, db)
    except Exception:
        if target is not None:
            target.rename(folder)               # 花名册没改成，把文件夹搬回去，不留半成品
        raise
    return target


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from agents.store import register_bot, set_members, list_members
    from .create import create_bot
    from .registry import all_bots

    with tempfile.TemporaryDirectory() as tmp:        # 在临时文件夹里试，不碰真的工作区
        db, bots_dir = Path(tmp) / "state.db", Path(tmp) / "bots"
        register_bot("main", "小牛", "主 bot", db)
        first = create_bot("英语老师", db=db, bots_dir=bots_dir)
        second = create_bot("旺财", db=db, bots_dir=bots_dir)
        set_members("feishu:群1", "feishu", ["main", first.id, second.id], db)
        print(first.id, second.id, file_count(first.id, bots_dir))      # 应该：bot-1 bot-2 2

        where = delete_bot(first.id, db, bots_dir)
        print(where.parent.name, where.name.split("__")[0], sorted(p.name for p in where.iterdir()))   # 应该：trash bot-1 ['AGENT.md', 'MEMORY.md']
        print([b.id for b in all_bots(db)], list_members("feishu:群1", db))   # 应该：['main', 'bot-2'] ['main', 'bot-2']
        print(sorted(p.name for p in bots_dir.iterdir()))                    # 应该：['bot-2']
        print(create_bot("新来的", db=db, bots_dir=bots_dir).id)              # 应该：bot-3，删掉的 bot-1 不再用

        for bad in ["main", "bot-1", "没有这个"]:
            try:
                delete_bot(bad, db, bots_dir)
                print("没拦住：", bad)
            except ValueError as exc:
                print("拒绝：", exc)                                           # 应该：3 个都被拒绝
