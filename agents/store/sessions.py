import json
import sqlite3
from datetime import date
from pathlib import Path
from config import STATE_DB, DB_BACKUPS

# 数据库 state.db：记"有哪些 Agent、有哪些会话、每个会话里有谁"。
# 人设和记忆不在这里，它们还是工作区里的 md 文件。
#
# 规矩：SQL 只写在 agents/store/ 这个文件夹里，别的代码调这里的函数。
# 以后要换成 PostgreSQL，只改这个文件夹。

KEEP_BACKUPS = 7      # 备份留最近几份

# owner 列是给"多人共用一台服务器"留的位置。现在一份安装只有一个用户，永远是 local。
SCHEMA = """
CREATE TABLE IF NOT EXISTS bots (
    id          TEXT PRIMARY KEY,                -- 英文编号，也是它的文件夹名，比如 main
    name        TEXT NOT NULL,                   -- 用户取的名字，比如 小牛
    description TEXT NOT NULL DEFAULT '',        -- 一句话说明它是干什么的
    model       TEXT NOT NULL DEFAULT '',        -- 空着表示用 config 里的默认模型
    packs       TEXT NOT NULL DEFAULT '[]',      -- 启用的能力包，JSON 列表
    owner       TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS sessions (
    id          TEXT PRIMARY KEY,                -- 比如 cli:default、feishu:群编号
    channel     TEXT NOT NULL,                   -- 从哪个入口来：cli、feishu、web
    owner       TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
);

CREATE TABLE IF NOT EXISTS session_members (
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    bot_id      TEXT NOT NULL REFERENCES bots(id),
    owner       TEXT NOT NULL DEFAULT 'local',
    joined_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (session_id, bot_id)             -- 同一个 Agent 不能在一个会话里出现两次
);

CREATE TABLE IF NOT EXISTS guests (
    id          TEXT PRIMARY KEY,                -- 编号，也是他的文件夹名，比如 guest-1
    channel     TEXT NOT NULL,                   -- 在哪个入口认识的：feishu
    contact     TEXT NOT NULL,                   -- 他在那个入口里的编号（飞书里是 ou_ 开头的那串）
    name        TEXT NOT NULL,                   -- 他的名字
    owner       TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    UNIQUE (channel, contact)                    -- 同一个人只登记一次，换了群还是他
);

CREATE TABLE IF NOT EXISTS session_guests (
    session_id  TEXT NOT NULL REFERENCES sessions(id),
    guest_id    TEXT NOT NULL REFERENCES guests(id),
    owner       TEXT NOT NULL DEFAULT 'local',
    joined_at   TEXT NOT NULL DEFAULT (datetime('now', 'localtime')),
    PRIMARY KEY (session_id, guest_id)
);
"""


def connect(path=STATE_DB):
    """打开数据库。文件不存在就新建，表不存在就建表。用完要 close()。"""
    if str(path) != ":memory:":
        Path(path).parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(path)
    conn.row_factory = sqlite3.Row               # 取出来的行可以用列名读：row["name"]
    conn.execute("PRAGMA foreign_keys = ON")     # 成员名单里不许出现不存在的会话或 Agent
    conn.executescript(SCHEMA)
    return conn


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


def backup_db(path=STATE_DB, folder=DB_BACKUPS):
    """把数据库另存一份：一天一份，只留最近 7 份。数据库还不存在就什么都不做。"""
    path = Path(path)
    if not path.exists():
        return None
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / f"state.db.{date.today().isoformat()}.bak"
    source = sqlite3.connect(path)
    copy = sqlite3.connect(target)
    try:
        source.backup(copy)      # SQLite 自带的备份：就算别处正在写，拷出来的也是完整的一份
    finally:
        copy.close()
        source.close()
    for old in sorted(folder.glob("state.db.*.bak"))[:-KEEP_BACKUPS]:
        old.unlink()
    return target


if __name__ == "__main__":
    conn = connect(":memory:")      # 只在内存里建一个临时数据库，不碰真的 state.db

    # 问号是占位符，值单独传进去，和 Java 的 PreparedStatement 一样，防 SQL 注入
    conn.execute("INSERT INTO bots (id, name, description) VALUES (?, ?, ?)", ("main", "小牛", "主 bot"))
    conn.execute("INSERT INTO sessions (id, channel) VALUES (?, ?)", ("cli:default", "cli"))
    conn.execute("INSERT INTO session_members (session_id, bot_id) VALUES (?, ?)", ("cli:default", "main"))

    row = conn.execute("SELECT * FROM bots WHERE id = ?", ("main",)).fetchone()
    print(row["id"], row["name"], row["owner"], row["packs"])      # 应该：main 小牛 local []

    members = conn.execute("SELECT bot_id FROM session_members WHERE session_id = ?", ("cli:default",)).fetchall()
    print([m["bot_id"] for m in members])                           # 应该：['main']

    try:
        conn.execute("INSERT INTO bots (id, name) VALUES (?, ?)", ("main", "另一个"))
    except sqlite3.IntegrityError:
        print("拒绝：编号 main 已经有了")                              # 应该：拒绝

    try:
        conn.execute("INSERT INTO session_members (session_id, bot_id) VALUES (?, ?)", ("cli:default", "ghost"))
    except sqlite3.IntegrityError:
        print("拒绝：没有 ghost 这个 Agent，不能加进会话")              # 应该：拒绝

    conn.close()
