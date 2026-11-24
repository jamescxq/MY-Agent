import json
from config import STATE_DB
from .db import connect

# Agent 的档案（花名册）：bots 表。表的定义在 db.py。


def register_bot(bot_id, name, description="", path=STATE_DB):
    """在花名册里登记一个 Agent。已经登记过就什么都不做，返回 False。"""
    conn = connect(path)
    try:
        cursor = conn.execute(
            "INSERT OR IGNORE INTO bots (id, name, description) VALUES (?, ?, ?)",
            (bot_id, name, description),
        )
        conn.commit()               # 提交了才真的写进文件
        return cursor.rowcount == 1
    finally:
        conn.close()


def list_bots(path=STATE_DB):
    """花名册里的全部 Agent，按登记的先后排。每个是一个字典，比如 {"id": "main", "name": "小牛", ...}"""
    conn = connect(path)
    try:
        rows = conn.execute("SELECT * FROM bots ORDER BY rowid").fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def rename_bot(bot_id, name, path=STATE_DB):
    """改花名册里的名字。"""
    conn = connect(path)
    try:
        conn.execute("UPDATE bots SET name = ? WHERE id = ?", (name, bot_id))
        conn.commit()
    finally:
        conn.close()


def remove_bot(bot_id, path=STATE_DB):
    """把一个 Agent 从花名册里去掉，同时从所有会话的成员名单里去掉，它定的定时提醒也一起删。它的文件夹不归这里管。"""
    conn = connect(path)
    try:
        # 成员名单里的行指着花名册里的行，所以要先删名单，再删花名册
        conn.execute("DELETE FROM schedules WHERE bot_id = ?", (bot_id,))
        conn.execute("DELETE FROM session_members WHERE bot_id = ?", (bot_id,))
        conn.execute("DELETE FROM bots WHERE id = ?", (bot_id,))
        conn.commit()
    finally:
        conn.close()


def set_description(bot_id, description, path=STATE_DB):
    """改花名册里那句"它是干什么的"。"""
    conn = connect(path)
    try:
        conn.execute("UPDATE bots SET description = ? WHERE id = ?", (description, bot_id))
        conn.commit()
    finally:
        conn.close()


def set_packs(bot_id, packs, path=STATE_DB):
    """改花名册里"启用的能力包"。packs 是一个列表，存的时候转成一段 JSON 文字。"""
    conn = connect(path)
    try:
        conn.execute("UPDATE bots SET packs = ? WHERE id = ?", (json.dumps(packs), bot_id))
        conn.commit()
    finally:
        conn.close()
