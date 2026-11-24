from config import GUESTS_DIR, STATE_DB, TEMPLATES
from agents.store import add_guest
from agents.prompt.texts import prompt_text

# 访客：用户请进会话、可以和 Agent 说话的其他人（比如飞书群里的另一个真人）。
#
# 规矩：
#   1. 访客不是用户。他的话在共享记录里标成【访客·名字】。他可以聊天，也可以让 Agent 干活。
#   2. 每位访客有一个自己的文件夹 guests/<编号>/：里面的 MEMORY.md 记关于他的事，所有 Agent 共用；
#      给他干活产生的文件也放在这里。关于访客的事不记进用户的 user/。
#   3. 访客能让 Agent 做的事和用户差不多（用户 2026-11-18 决定放开）：改文件、发通知都可以。
#      代码里还拦着的（agents/permission/ 和入口）：
#        - 命令只有用户能用（新建、删除 Agent，开关能力，/stop）
#        - 访客说话时碰不到别的访客的文件夹
#        - 工具用允许名单（gate.py 的 GUEST_TOOLS），以后新加的工具默认访客用不了
#        - 定时提醒：访客能查看、删除，不能新定（gate.py 的 GUEST_ACTIONS）
#   4. 分清"谁的事记在哪"现在只靠提示词：访客的事记在他自己的 MEMORY.md，不记进 user/。
# 这个文件不认识飞书：访客是从哪个入口来的、他在那个入口里的编号是什么，由入口传进来。


def guest_label(name):
    """访客的话在共享记录里标成谁说的。"""
    return f"访客·{name}"


def memory_path(guest_id):
    """这位访客的记忆文件，写法和工具里用的路径一样。"""
    return f"guests/{guest_id}/MEMORY.md"


def invite_guest(session_id, channel, contact, name, db=STATE_DB, folder=GUESTS_DIR):
    """把一个人请成这个会话的访客：在花名册里登记，给他建好记忆文件夹。返回他的档案（字典）。

    以前请过他，就还是原来的编号和原来的记忆，不会覆盖。
    """
    guest = add_guest(session_id, channel, contact, name, db)
    home = folder / guest["id"]
    home.mkdir(parents=True, exist_ok=True)
    target = home / "MEMORY.md"
    if not target.exists():
        template = (TEMPLATES / "guest" / "MEMORY.md").read_text(encoding="utf-8")
        target.write_text(template + f"- 名字：{name}\n", encoding="utf-8")
    return guest


def guest_rule(guests, alone, folder=GUESTS_DIR):
    """会话里有访客时，加在每个成员提示词后面的规则，后面附上每位访客的记忆。

    alone=True 表示这个会话里只有一个 Agent：这时用户的话前面没有标记。
    规则的原文在 templates/prompts/guest.md，里面有一个空 {who}，按有几个 Agent 填下面两句里的一句。
    """
    who = "没有标记的话是用户说的。" if alone else "【用户】才是用户。"
    lines = ["\n\n" + prompt_text("guest", who=who)]
    for guest in guests:
        lines.append(f"- {guest['name']}：文件夹 guests/{guest['id']}/，记忆文件 {memory_path(guest['id'])}")
    for guest in guests:
        target = folder / guest["id"] / "MEMORY.md"
        if target.is_file():
            text = target.read_text(encoding="utf-8")
            lines.append(f'\n<file name = "{memory_path(guest["id"])}">\n{text}\n</file>')
    return "\n".join(lines)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:       # 临时文件夹里试，不碰真的工作区
        db, folder = Path(tmp) / "state.db", Path(tmp) / "guests"
        first = invite_guest("feishu:群1", "feishu", "ou_aaa", "张三", db, folder)
        again = invite_guest("feishu:群2", "feishu", "ou_aaa", "张三", db, folder)
        other = invite_guest("feishu:群1", "feishu", "ou_bbb", "李四", db, folder)
        print(first["id"], again["id"], other["id"])        # 应该：guest-1 guest-1 guest-2，同一个人换了群还是同一份
        print(sorted(p.name for p in folder.iterdir()))     # 应该：['guest-1', 'guest-2']
        print(guest_rule([first, other], alone=False, folder=folder))
