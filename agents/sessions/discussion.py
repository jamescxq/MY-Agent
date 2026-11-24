from dataclasses import dataclass, field
from agents.prompt.texts import prompt_text

# 一个会话里有多个 Agent 时，它们怎么轮流说话（自由讨论）。
#
# 规则：
#   1. 会话里有一份共享记录，每句话标明是谁说的。
#   2. 用户的话里点了某个成员的名字，只让被点到的看；没点名，所有成员都看。
#   3. 轮到谁看，谁就决定接不接话。不接就输出 [不回复]。
#   4. 有人接了话：话里点了别的成员的名字，下一轮让被点到的看；
#      没点名，就只让第 2 条里那些人看（没被叫到的成员不打扰）。没有新的话可看，讨论结束。
#   5. 会话里还可以有访客（用户请进来的其他人，见 guests.py）。访客的话标成【访客·名字】，
#      谁看、谁接话的规则和用户的话一样。
#   6. 两道闸：成员之间最多来回 MAX_ROUNDS 轮；用户说一句话，所有成员加起来最多看 MAX_TURNS 次。
#      另外入口可以随时喊停（飞书里是 /stop）。
#
# Agent 之间的话只在这里传，不经过飞书再绕回来，所以不会出现机器人互相触发停不下来。
# 这个文件不认识飞书，也不调模型：怎么调模型（run）、怎么把话发出去（emit）由入口传进来。

NO_REPLY = "[不回复]"
USER = "用户"
MAX_ROUNDS = 10        # 用户说一句话以后，最多几轮
MAX_TURNS = 20         # 用户说一句话以后，所有成员加起来最多看几次（每看一次调一次模型）
LIMIT_NOTICE = "（这件事他们已经说了好几轮，先停在这里。要继续就再说一句。）"


@dataclass
class Member:
    ctx: object                 # 它的工牌
    name: str                   # 它的名字
    system: str                 # 它的提示词
    tools: list                 # 它能用的工具
    messages: list = field(default_factory=list)    # 它自己的对话历史
    seen: int = 0               # 共享记录里，它已经看到第几条了


def group_rule(name, names):
    """会话里有多个 Agent 时，加在每个成员提示词后面的规则。原文在 templates/prompts/group.md。"""
    return "\n\n" + prompt_text("group", name=name, names="、".join(names)) + "\n"


class Room:
    """一个会话：里面的成员，和大家共享的那份记录。"""

    def __init__(self, members):
        self.members = members
        self.log = []                       # 共享记录，每条是 (谁说的, 说了什么)
        for member in members:
            member.seen = 0

    def listeners(self, speaker, text, audience):
        """这句话该让谁看：点了名字的只让被点到的看；没点名，就让 audience 里的其他人看。"""
        named = [member for member in self.members if member is not speaker and member.name in text]
        return named or [member for member in audience if member is not speaker]

    def render(self, lines):
        """把几条记录变成给模型看的文字。只有一个成员时用户的话不加【】，和单独对话一样；访客的话总是加。"""
        if len(self.members) == 1:
            return "\n\n".join(text if speaker == USER else f"【{speaker}】{text}" for speaker, text in lines)
        return "\n\n".join(f"【{speaker}】{text}" for speaker, text in lines)

    def wake(self, member, content, run, emit):
        """代码主动叫一个成员开口（不是谁说了话引起的）。新成员打招呼、定时提醒到点，都走这里。

        content 是代码替用户说的那句话，只给它一个人看，不进共享记录；
        它说的话进共享记录，别的成员下次看的时候能看到，但不会因为这句话被叫起来。
        """
        reply = run(member, content)
        if reply is None:
            return
        self.log.append((member.name, reply))
        if member in self.members:
            member.seen = len(self.log)
        emit(member, reply)

    def greet(self, member, opening, run, emit):
        """让一个新成员先开口打招呼。opening 是开场指令。"""
        self.wake(member, opening, run, emit)

    def discuss(self, text, run, emit, stopped=lambda: False, speaker=USER):
        """有人说了一句话，让成员们讨论。

        speaker               这句话是谁说的，默认是用户；访客说的就传他的标记（guests.py 的 guest_label）
        run(member, content)  让这个成员看 content，返回它说的话；它不接话时返回 None
        emit(member, reply)   把它说的话发出去
        stopped()             用户有没有喊停
        返回要另外告诉用户的一句提示；正常结束返回 None。
        """
        self.log.append((speaker, text))
        # 这句话是说给谁听的：点了名就是被点到的，没点名就是所有成员。
        # 之后 Agent 说的话如果没点名，也只让这些人看，不去打扰没被叫到的成员。
        audience = self.listeners(None, text, self.members)
        waiting = audience
        turns = 0
        for _ in range(MAX_ROUNDS):
            if not waiting:
                return None
            upcoming = []                   # 下一轮该谁看
            for member in self.members:
                if member not in waiting:
                    continue
                unseen = self.log[member.seen:]         # 只给它看还没看过的
                if not unseen:                          # 没有新的话，不用为它调模型
                    continue
                if stopped():
                    return None
                if turns >= MAX_TURNS:
                    return LIMIT_NOTICE
                turns += 1
                reply = run(member, self.render(unseen))
                member.seen = len(self.log)
                if reply is None:
                    continue
                self.log.append((member.name, reply))
                member.seen = len(self.log)             # 自己说的话不用再看一遍
                emit(member, reply)
                for other in self.listeners(member, reply, audience):
                    if other not in upcoming:
                        upcoming.append(other)
            waiting = upcoming
        return LIMIT_NOTICE if waiting else None


if __name__ == "__main__":
    # 用三个假成员试规则，不调模型
    def fake_member(name):
        return Member(ctx=None, name=name, system="", tools=[])

    def show(member, reply):
        print(f"    【{member.name}】{reply}")

    scripts = {}                            # 每个成员按顺序说什么；说完了就不再接话
    looked = []                             # 记下每次是谁在看

    def run(member, content):
        looked.append(member.name)
        lines = scripts.get(member.name, [])
        return lines.pop(0) if lines else None

    def play(title, text, script):
        scripts.clear()
        scripts.update(script)
        looked.clear()
        print(title)
        room = Room([fake_member("小牛"), fake_member("二牛"), fake_member("网申助手")])
        notice = room.discuss(text, run, show)
        print("    看过的顺序：", looked, "| 提示：", notice)

    play("1 点名：只有二牛看，调 1 次模型", "二牛，你叫啥", {"二牛": ["我叫二牛"]})
    play("2 不点名：三个各看一次，调 3 次", "大家好", {"小牛": ["你好"]})
    play("3 都不接话：一轮就结束，调 3 次", "嗯", {})
    play("4 二牛点了网申助手的名：网申助手接着看，然后二牛再看它的回答", "二牛，这事谁负责", {"二牛": ["网申助手负责"], "网申助手": ["是我"]})
    play(f"5 互相客套停不下来：被闸拦住，最多 {MAX_TURNS} 次", "你们聊", {"小牛": ["a"] * 9, "二牛": ["b"] * 9, "网申助手": ["c"] * 9})
    play("6 排在后面的先看到了前面的回答，不会为同一句话再看一遍", "大家说说", {"二牛": ["我先说"]})

    print("7 访客说话：规则和用户一样，只是标记换成【访客·张三】。没点名两个都看，点了二牛只有二牛看")
    room = Room([fake_member("小牛"), fake_member("二牛")])

    def peek(member, content):
        print("   ", member.name, "看到：", content.split())

    room.discuss("今天天气不错", peek, show, speaker="访客·张三")
    room.discuss("二牛你好", peek, show, speaker="访客·张三")
