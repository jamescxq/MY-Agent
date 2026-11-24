from config import STATE_DB
from .db import connect

# 定时提醒：schedules 表。表的定义在 db.py。
# 这里只管存和取，不管时间怎么算：时间由 agents/events/scheduler.py 算好了传进来。
# 时间都写成 "2026-11-24 15:00" 这样的文字。这种写法按字典序比大小，正好就是按时间先后比，
# 所以 SQL 里可以直接写 next_run <= 现在。


def add_schedule(session_id, bot_id, kind, at, task, next_run, path=STATE_DB):
    """记下一件定时的事，返回它的编号。"""
    conn = connect(path)
    try:
        cursor = conn.execute(
            "INSERT INTO schedules (session_id, bot_id, kind, at, task, next_run) VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, bot_id, kind, at, task, next_run),
        )
        conn.commit()
        return cursor.lastrowid
    finally:
        conn.close()


def list_schedules(session_id, path=STATE_DB):
    """这个会话里定了哪些，按下一次该做的时间排。每个是一个字典。"""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE session_id = ? ORDER BY next_run, id", (session_id,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def remove_schedule(schedule_id, session_id, path=STATE_DB):
    """删掉一条。只能删这个会话里定的，删成了返回 True，没有这一条返回 False。"""
    conn = connect(path)
    try:
        cursor = conn.execute(
            "DELETE FROM schedules WHERE id = ? AND session_id = ?", (schedule_id, session_id)
        )
        conn.commit()
        return cursor.rowcount == 1
    finally:
        conn.close()


def due_schedules(now, path=STATE_DB):
    """现在已经到点的那些（所有会话的都算）。now 是 "2026-11-24 15:00" 这样的文字。"""
    conn = connect(path)
    try:
        rows = conn.execute(
            "SELECT * FROM schedules WHERE next_run <= ? ORDER BY next_run, id", (now,)
        ).fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()


def finish_schedule(schedule_id, next_run, path=STATE_DB):
    """一件事做完了。next_run 是 None：只做一次的，删掉；不是 None：每天做的，把下一次的时间记上。"""
    conn = connect(path)
    try:
        if next_run is None:
            conn.execute("DELETE FROM schedules WHERE id = ?", (schedule_id,))
        else:
            conn.execute("UPDATE schedules SET next_run = ? WHERE id = ?", (next_run, schedule_id))
        conn.commit()
    finally:
        conn.close()


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:          # 临时数据库，不碰真的 state.db
        db = Path(tmp) / "state.db"
        a = add_schedule("feishu:群一", "main", "once", "2026-11-24 15:00", "提醒投简历", "2026-11-24 15:00", db)
        b = add_schedule("feishu:群一", "bot-1", "daily", "08:00", "说早安", "2026-11-25 08:00", db)
        add_schedule("feishu:群二", "main", "daily", "09:00", "别的群的事", "2026-11-25 09:00", db)
        print(a, b, [row["task"] for row in list_schedules("feishu:群一", db)])      # 应该：1 2 ['提醒投简历', '说早安']
        print([row["task"] for row in due_schedules("2026-11-24 14:59", db)])       # 应该：[]，还没到点
        print([row["task"] for row in due_schedules("2026-11-24 15:00", db)])       # 应该：['提醒投简历']
        print([row["task"] for row in due_schedules("2026-11-25 08:30", db)])       # 应该：['提醒投简历', '说早安']，别的群 9 点的还没到
        finish_schedule(a, None, db)                    # 只做一次的：删掉
        finish_schedule(b, "2026-11-26 08:00", db)      # 每天做的：记上明天
        print([(row["task"], row["next_run"]) for row in list_schedules("feishu:群一", db)])   # 应该：[('说早安', '2026-11-26 08:00')]
        print(remove_schedule(b, "feishu:群二", db), remove_schedule(b, "feishu:群一", db))    # 应该：False True，别的会话删不了
