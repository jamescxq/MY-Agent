import re
import shutil
from config import STATE_DB, BOTS_DIR, TEMPLATES
from agents.store import register_bot
from .profile import Profile, PLACEHOLDER
from .registry import all_bots

# 新建一个专属 Agent。命令行的 /new、以后飞书的 /new、网页的按钮、Agent 手里的"新建"工具，
# 调的都是这里的 create_bot()，所以从哪个入口建，结果都一样。

MAX_NAME = 20                                     # 名字最多几个字
BAD_CHARS = '/\\:*?"<>|'                          # 名字里不许有的符号
ID_PATTERN = re.compile(r"^[a-z0-9][a-z0-9-]{0,31}$")    # 编号只许小写字母、数字、横线
# Windows 不许用这些词当文件夹名
RESERVED_IDS = {"con", "prn", "aux", "nul"} | {f"com{i}" for i in range(1, 10)} | {f"lpt{i}" for i in range(1, 10)}


def check_name(name, bots):
    """检查用户给的名字。有问题返回一句说明，没问题返回 None。"""
    if not name:
        return "名字不能是空的"
    if len(name) > MAX_NAME:
        return f"名字太长了，最多 {MAX_NAME} 个字"
    if any(ch in BAD_CHARS or not ch.isprintable() for ch in name):
        return f"名字里不能有这些符号：{BAD_CHARS}"
    if not any(ch.isalnum() for ch in name):
        return "名字里至少要有一个字、字母或数字"
    key = name.casefold()
    for bot in bots:
        if key in (bot.id.casefold(), bot.name.casefold()):
            return f"已经有一个叫「{bot.name}」的 Agent 了，换一个名字"
    return None


def make_id(name, bots, bots_dir):
    """给新 Agent 起一个英文编号，它也是文件夹名。

    名字本身就是合法的英文编号（比如 coder）就直接用；否则用 bot-1、bot-2……
    用户输入的名字不直接当文件夹名：里面可能有 .. 这样的危险写法。
    """
    taken = {bot.id for bot in bots}
    candidate = name.lower()
    if ID_PATTERN.match(candidate) and candidate not in taken | RESERVED_IDS and not (bots_dir / candidate).exists():
        return candidate
    number = 1
    while f"bot-{number}" in taken or (bots_dir / f"bot-{number}").exists():
        number += 1
    return f"bot-{number}"


def create_bot(name, description="", db=STATE_DB, bots_dir=BOTS_DIR):
    """新建一个 Agent：建文件夹、放空白档案、在花名册里登记。返回它的档案。

    名字不合格时抛出 ValueError，里面是给用户看的说明。
    """
    name = name.strip()
    bots = all_bots(db)
    problem = check_name(name, bots)
    if problem:
        raise ValueError(problem)

    bot_id = make_id(name, bots, bots_dir)
    folder = bots_dir / bot_id
    folder.mkdir(parents=True)                    # 已经存在会报错，不会盖掉别人的文件夹
    try:
        agent_md = (TEMPLATES / "bot" / "AGENT.md").read_text(encoding="utf-8")
        (folder / "AGENT.md").write_text(agent_md.replace(PLACEHOLDER, name), encoding="utf-8")
        shutil.copy(TEMPLATES / "bot" / "MEMORY.md", folder / "MEMORY.md")
        if not register_bot(bot_id, name, description, db):
            raise ValueError(f"编号 {bot_id} 已经被占用了，再试一次")
    except Exception:
        shutil.rmtree(folder)                     # 没建成就把刚建的文件夹收拾掉，不留半成品
        raise
    return Profile(id=bot_id, name=name, description=description)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from agents.store import register_bot as register

    with tempfile.TemporaryDirectory() as tmp:        # 在临时文件夹里试，不碰真的工作区
        db = Path(tmp) / "state.db"
        bots_dir = Path(tmp) / "bots"
        register("main", "小牛", "主 bot", db)

        bot = create_bot("编程工程师", db=db, bots_dir=bots_dir)
        print(bot.id, bot.name, sorted(p.name for p in (bots_dir / bot.id).iterdir()))   # 应该：bot-1 编程工程师 ['AGENT.md', 'MEMORY.md']
        print(create_bot("Coder", db=db, bots_dir=bots_dir).id)       # 应该：coder，名字本身能当编号
        print(create_bot("英语老师", db=db, bots_dir=bots_dir).id)     # 应该：bot-2

        for bad in ["..", "", "a/b", "小牛", "MAIN", "编程工程师", "一" * 21, "---"]:
            try:
                create_bot(bad, db=db, bots_dir=bots_dir)
                print("没拦住：", bad)
            except ValueError as exc:
                print("拒绝：", exc)                                    # 应该：8 个都被拒绝

        print([b.id for b in all_bots(db)])                           # 应该：['main', 'bot-1', 'coder', 'bot-2']
        print(sorted(p.name for p in bots_dir.iterdir()))             # 应该：['bot-1', 'bot-2', 'coder']，没有多余的文件夹
