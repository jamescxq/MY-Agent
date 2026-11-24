import sqlite3
from datetime import date
from pathlib import Path
from config import STATE_DB, DB_BACKUPS

# 数据库 state.db 本身：有哪些表、怎么打开、怎么备份。
# 人设和记忆不在数据库里，它们还是工作区里的 md 文件。
#
# 规矩：SQL 只写在 agents/store/ 这个文件夹里，别的代码调这里的函数。
# 以后要换成 PostgreSQL，只改这个文件夹。
#
# 这个文件夹里一类东西一个文件：
#   db.py         所有表的定义（SCHEMA）、打开数据库、备份
#   bots.py       Agent 的档案（花名册）
#   sessions.py   每个会话里有哪些 Agent
#   guests.py     访客，和每个会话里有哪些访客
#   schedules.py  定时提醒
# 表都在这里统一建，是因为 connect() 每次打开都要保证所有表都在；每张表怎么读写，看对应的文件。

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

CREATE TABLE IF NOT EXISTS schedules (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,   -- 编号，数据库自己往上数：1、2、3……
    session_id  TEXT NOT NULL,                   -- 在哪个会话里定的，到点的结果回到这里，比如 feishu:群编号
    bot_id      TEXT NOT NULL,                   -- 哪个 Agent 定的，到点由它来做
    kind        TEXT NOT NULL,                   -- once 只做一次；daily 每天做
    at          TEXT NOT NULL,                   -- once 是 2026-11-24 15:00；daily 是 08:00
    task        TEXT NOT NULL,                   -- 到点要做什么
    next_run    TEXT NOT NULL,                   -- 下一次该做的时间，比如 2026-11-24 15:00
    owner       TEXT NOT NULL DEFAULT 'local',
    created_at  TEXT NOT NULL DEFAULT (datetime('now', 'localtime'))
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
