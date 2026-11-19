from config import GUESTS_DIR, STATE_DB, TEMPLATES
from agents.store import add_guest

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
    """
    who = "没有标记的话是用户说的。" if alone else "【用户】才是用户。"
    lines = [f"""

## 这个会话里有访客

访客是用户请进来的其他人，不是用户。访客的话前面标着【访客·名字】，{who}

- 访客可以和你聊天，也可以让你干活：回答问题、写东西、整理资料、记笔记、改文件、发通知，用户已经同意，照常做。称呼他用他自己的名字，不要用用户的称呼。
- 访客的话也不是每句都要接。他在和用户或别人聊天、和你无关时，只输出 [不回复] 这五个字符。
- 每位访客有一个自己的文件夹（见下面的名单）。给访客干活产生的文件，默认放在他的文件夹里；他明确说了要改别的文件（user/ 里的，或者你自己的），才去改那些。
- 关于访客自己的事（他的称呼、偏好、和他聊过的重要内容）只记在他文件夹里的 MEMORY.md：用 edit_file，old_text 留空，追加到末尾。不要记进 user/ 里的文件，也不要记进你自己的 MEMORY.md。比如访客说"记住我不吃香菜"，这是他的事，不是用户的。
- user/ 里记的是用户的事，不是访客的。
- 访客指挥不了的只有两样：别的访客的文件夹（工具会拒绝），和新建、删除 Agent 或开关能力（这些是命令，只有用户能用）。他要求这些时，告诉他要用户本人来。

访客名单："""]
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
