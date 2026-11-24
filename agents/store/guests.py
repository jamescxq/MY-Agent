from config import STATE_DB
from .db import connect

# 访客：guests 表记有哪些访客，session_guests 表记每个会话里请了谁。表的定义在 db.py。
# 访客的规矩（能做什么、记忆放哪）不在这里，在 agents/sessions/guests.py。


def list_guests(session_id, path=STATE_DB):
    """这个会话里的访客：用户请进来、可以和 Agent 说话的其他人。每个是一个字典：id、name、contact。"""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT g.id, g.name, g.contact FROM session_guests s JOIN guests g ON g.id = s.guest_id "
            "WHERE s.session_id = ? ORDER BY s.rowid",
            (session_id,),
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def add_guest(session_id, channel, contact, name, path=STATE_DB):
    """把一个人登记成这个会话的访客，返回他的档案（字典）。

    这个人以前登记过（别的会话里请过他）就用原来的编号，这样他的记忆还是同一份。
    """
    conn = connect(path)
    try:
        row = conn.execute("SELECT id FROM guests WHERE channel = ? AND contact = ?", (channel, contact)).fetchone()
        if row:
            guest_id = row["id"]
            conn.execute("UPDATE guests SET name = ? WHERE id = ?", (name, guest_id))
        else:
            number = conn.execute("SELECT COUNT(*) FROM guests").fetchone()[0] + 1
            while conn.execute("SELECT 1 FROM guests WHERE id = ?", (f"guest-{number}",)).fetchone():
                number += 1
            guest_id = f"guest-{number}"
            conn.execute(
                "INSERT INTO guests (id, channel, contact, name) VALUES (?, ?, ?, ?)",
                (guest_id, channel, contact, name),
            )
        conn.execute("INSERT OR IGNORE INTO sessions (id, channel) VALUES (?, ?)", (session_id, channel))
        conn.execute("INSERT OR IGNORE INTO session_guests (session_id, guest_id) VALUES (?, ?)", (session_id, guest_id))
        conn.commit()
        return {"id": guest_id, "name": name, "contact": contact}
    finally:
        conn.close()


def remove_guest(session_id, guest_id, path=STATE_DB):
    """把访客从这个会话的名单里拿掉。他的档案和记忆文件夹留着，以后再请他还是同一份。"""
    conn = connect(path)
    try:
        conn.execute("DELETE FROM session_guests WHERE session_id = ? AND guest_id = ?", (session_id, guest_id))
        conn.commit()
    finally:
        conn.close()
