from config import STATE_DB, BOTS_DIR
from agents.store import list_bots, rename_bot
from .profile import from_row, read_name

# 花名册：有哪些 Agent。数据存在数据库的 bots 表里，这里不写 SQL，只调 agents/store 的函数。


def all_bots(db=STATE_DB):
    """全部 Agent 的档案，按新建的先后排。"""
    return [from_row(row) for row in list_bots(db)]


def find_bot(text, db=STATE_DB):
    """按名字或编号找一个 Agent，不分大小写。找不到返回 None。"""
    key = text.strip().casefold()
    for bot in all_bots(db):
        if key in (bot.id.casefold(), bot.name.casefold()):
            return bot
    return None


def sync_names(db=STATE_DB, bots_dir=BOTS_DIR):
    """名字以每个 Agent 的 AGENT.md 为准。用户让它改过名的话，启动时把花名册里的名字也改过来。"""
    for bot in all_bots(db):
        name = read_name(bots_dir / bot.id)
        if name and name != bot.name:
            rename_bot(bot.id, name, db)
