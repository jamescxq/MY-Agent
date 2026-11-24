from config import STATE_DB
from .db import connect

# 会话的成员名单：sessions 表记有哪些会话，session_members 表记每个会话里有哪些 Agent。表的定义在 db.py。


def list_members(session_id, path=STATE_DB):
    """这个会话的成员名单：里面有哪些 Agent，返回编号的列表，按加入的先后排。没有记录返回空列表。"""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT bot_id FROM session_members WHERE session_id = ? ORDER BY rowid",
            (session_id,),
        ).fetchall()
        return [row["bot_id"] for row in rows]
    finally:
        conn.close()


def set_members(session_id, channel, bot_ids, path=STATE_DB):
    """把这个会话的成员名单整个换成 bot_ids。先清掉旧的，再按顺序写新的。"""
    conn = connect(path)
    try:
        conn.execute("INSERT OR IGNORE INTO sessions (id, channel) VALUES (?, ?)", (session_id, channel))
        conn.execute("DELETE FROM session_members WHERE session_id = ?", (session_id,))
        for bot_id in bot_ids:
            conn.execute("INSERT INTO session_members (session_id, bot_id) VALUES (?, ?)", (session_id, bot_id))
        conn.commit()
    finally:
        conn.close()
