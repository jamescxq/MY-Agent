import shutil
from config import WORKSPACE, USER_DIR, BOTS_DIR, TEMPLATES
from agents.memory.backup import backup_workspace
from agents.store import register_bot, backup_db

# 工作区长什么样：
#   user/            用户层，所有 Agent 共用（USER.md、MEMORY.md）
#   bots/<编号>/     每个 Agent 自己的文件夹（AGENT.md、MEMORY.md、memory/）
#   state.db         数据库
# 这个文件负责：第一次运行时把它建好；旧结构（所有文件都堆在根目录）自动搬成新结构。

MAIN = "main"                                                     # 主 bot 的编号
OLD_MARKERS = ["AGENT.md", "USER.md", "MEMORY.md", "BOOTSTRAP.md", "memory"]   # 根目录有这些，说明还是旧结构
TO_USER = ["USER.md", "MEMORY.md"]                                # 这两个搬到 user/，其它的都搬到 bots/main/
STAY = {"user", "bots", "skills", "db-backups", "schedules.json"}   # 这些留在根目录不动；点开头的（.git、.idea）也不动


def migrate_old_layout():
    """把旧结构搬成新结构。只移动，不复制、不删除、不覆盖。返回搬了哪些。"""
    if not WORKSPACE.exists():
        return []
    if not any((WORKSPACE / name).exists() for name in OLD_MARKERS):
        return []

    backup_workspace("搬成新结构之前的备份")       # 先在工作区的 git 里存一份，搬错了能找回来
    main = BOTS_DIR / MAIN
    USER_DIR.mkdir(exist_ok=True)
    main.mkdir(parents=True, exist_ok=True)

    moved = []
    for item in sorted(WORKSPACE.iterdir()):
        name = item.name
        if name.startswith(".") or name.lower() in STAY or name.lower().startswith("state.db"):
            continue
        target = (USER_DIR if name in TO_USER else main) / name
        if target.exists():
            print(f"【警告】{target} 已经有了，根目录的 {name} 没有搬，请手动处理")
            continue
        try:
            item.rename(target)
        except OSError as exc:
            print(f"【警告】{name} 没搬成（{exc}），下次启动会再试")
            continue
        moved.append(f"{name} → {target.relative_to(WORKSPACE).as_posix()}")
    return moved


def copy_if_missing(template, target):
    """模板复制到工作区。已经有的文件不覆盖。"""
    if not target.exists():
        shutil.copy(template, target)


def ensure_workspace():
    """启动时调用一次：搬旧结构、建文件夹、补上缺的模板、登记主 bot、备份数据库。"""
    moved = migrate_old_layout()
    if moved:
        print("【系统】工作区已搬成新结构：")
        for line in moved:
            print("   ", line)

    main = BOTS_DIR / MAIN
    is_new = not (main / "AGENT.md").exists()      # 没有人设，说明是第一次运行
    USER_DIR.mkdir(parents=True, exist_ok=True)
    main.mkdir(parents=True, exist_ok=True)

    copy_if_missing(TEMPLATES / "user" / "USER.md", USER_DIR / "USER.md")
    copy_if_missing(TEMPLATES / "user" / "MEMORY.md", USER_DIR / "MEMORY.md")
    copy_if_missing(TEMPLATES / "bot" / "AGENT.md", main / "AGENT.md")
    copy_if_missing(TEMPLATES / "bot" / "MEMORY.md", main / "MEMORY.md")
    if is_new:
        copy_if_missing(TEMPLATES / "bot" / "BOOTSTRAP.md", main / "BOOTSTRAP.md")

    try:
        register_bot(MAIN, "主 bot", "默认的 Agent，什么都可以找它")
        backup_db()
    except Exception as exc:
        print(f"【警告】数据库没准备好（{type(exc).__name__}：{exc}），不影响聊天")
