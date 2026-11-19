# 入口：飞书。你在飞书里发的消息交给 Agent，它的回复发回飞书。
# 一个飞书会话（群或单聊）有一份成员名单，默认只有主 bot。
# /bots 看有哪些，/join 名字 让它加入，/leave 名字 让它离开，/use 名字 只留一个，
# /new 名字 新建并加入，/packs 看能力，/stop 让它们停下。
#
# 谁的话算数：只有主人（FEISHU_OWNER_ID）能用命令。
# 群里别的人默认被忽略；主人用 /guest @某人 把他请成访客以后，他可以和 Agent 聊天、让 Agent 干活
# （包括改文件、发通知）：和主人说话一样，叫了名字只有被叫到的回答，没叫名字 Agent 们自己决定接不接。
# 他不能用命令，关于他的事记在他自己的文件夹里，他说话时 Agent 碰不到别的访客的文件夹。
# /guest 看访客名单，/unguest 名字 请他离开。规矩见 agents/sessions/guests.py。
#
# 飞书账号：收消息只靠主 bot 的那个应用机器人。别的 Agent 如果在 .env 里配了自己的应用机器人
# （见 config.py 的 feishu_app），就用自己的账号发消息，飞书里显示它自己的名字和头像；
# 没配的由主账号代发，开头带【名字】。
# 运行：python feishu_bot.py（要一直开着）
# 阶段 I 建了 MY-Agent-connectors 仓库以后，这个文件搬过去。
import json
import queue
import re
import threading
from dataclasses import replace

import anthropic
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_OWNER_ID, feishu_app
from agents.bots import all_bots, ctx_for, handle_session_command, ensure_workspace, is_fresh, OPENING, OPENING_NOTE
from agents.prompt.builder import assemble_prompt, get_agent_name
from agents.loop import run_agent
from agents.permission import describe
from agents.capabilities import tools_for
from agents.memory import write_daily, backup_workspace
from agents.context import trim_messages
from agents.store import list_members, set_members, list_guests, remove_guest
from agents.sessions import NO_REPLY, Member, Room, group_rule, guest_label, guest_rule, invite_guest

FEISHU_RULE = """

## 你现在在飞书里

用户正通过飞书和你对话，不在电脑前。

- 用户发的每一条消息你都能看到，但不是每一条都要回。用户只是随口说一句、自言自语，或者这句话明显不需要你接话时，只输出 [不回复] 这五个字符，不要加任何别的内容。
- 用户在问你、让你做事，或者你有对用户有用的话要说时，正常回复。拿不准就回复。
- 飞书里显示不了表格和标题这类格式，回复用纯文字，尽量短。
- 用户让你改文件（改一句、删一句、重写整个文件），直接做，不用先问。少数操作系统会自动在飞书里问用户同意不同意，你不用自己问；被拒绝时不要重试。
"""

inbox = queue.Queue()      # 收到的消息先放这里排队
seen = set()               # 处理过的消息编号，用来去重
rooms = {}                 # 会话编号 → 这个会话的成员和共享记录（Room）
solo = {}                  # (会话编号, Agent 编号) → 单独对话时的那个成员，切走再切回来接着聊
stop_requests = set()      # 用户发了 /stop 的会话，正在进行的讨论看到就停
api = None                 # 主 bot 的飞书账号：收消息靠它，别的 Agent 没有自己的账号时也由它代发
accounts = {}              # Agent 编号 → 它自己的飞书账号。.env 里配了的才有，没配的是 None
blocked = set()            # (会话编号, Agent 编号)：它的账号发不进这个会话（比如没被拉进群），改由主账号代发
MENTION = re.compile(r"^(@\S+\s+)+")    # 消息开头的 @某某：认命令之前先去掉
pending = {}               # 会话编号 → 正在等主人回答的那次审批（一个队列，主人的回答放进去）
APPROVAL_WAIT = 120        # 一次审批最多等主人多少秒，没等到算拒绝
YES = ("同意", "好", "可以", "行", "y", "yes", "ok")     # 主人回这些算同意


def make_approver(chat_id, who):
    """造一个审批函数，交给 run_agent 用：遇到要审批的操作，就在这个会话里问主人，等他回答。

    回"同意"才算同意；回别的、喊 /stop、或者太久没回，都算拒绝。只认主人的回答，访客说"同意"不算。
    who 是哪个 Agent 想做这件事。
    """
    def approver(name, args):
        box = queue.Queue()                # 主人的回答会被 on_message 放进这里
        pending[chat_id] = box
        send(chat_id, f"【要你点头】{who}想{describe(name, args)}。\n同意就回：同意。回别的，或者 {APPROVAL_WAIT // 60} 分钟没回，都算拒绝。")
        try:
            answer = box.get(timeout=APPROVAL_WAIT)
        except queue.Empty:
            send(chat_id, "没等到你的回答，这次算拒绝。")
            return False
        finally:
            pending.pop(chat_id, None)
        return answer.lower() in YES
    return approver


def post(account, chat_id, text):
    """用某个飞书账号往会话里发一条文字。返回 (成没成, 没成的原因)。"""
    body = (
        CreateMessageRequestBody.builder()
        .receive_id(chat_id)
        .msg_type("text")
        .content(json.dumps({"text": text}, ensure_ascii=False))
        .build()
    )
    request = (
        CreateMessageRequest.builder()
        .receive_id_type("chat_id")
        .request_body(body)
        .build()
    )
    response = account.im.v1.message.create(request)
    if response.success():
        return True, ""
    return False, f"{response.code} {response.msg}"


def send(chat_id, text):
    """用主 bot 的账号发一条消息。"""
    ok, why = post(api, chat_id, text)
    if not ok:
        print(f"【飞书】发送失败：{why}")


def make_account(app_id, secret):
    return lark.Client.builder().app_id(app_id).app_secret(secret).build()


def account_of(bot_id):
    """这个 Agent 自己的飞书账号。主 bot 就是 api；别的 Agent 要在 .env 里配过才有，没配返回 None。"""
    if bot_id == "main":
        return api
    if bot_id not in accounts:
        app = feishu_app(bot_id)
        accounts[bot_id] = make_account(*app) if app else None
    return accounts[bot_id]


def send_as(chat_id, bot_id, name, text):
    """让一个 Agent 说话。它有自己的飞书账号就用自己的发；没有，或者发不进这个会话，就由主账号代发并在开头带上【名字】。"""
    account = account_of(bot_id)
    if account is not None and (chat_id, bot_id) not in blocked:
        ok, why = post(account, chat_id, text)
        if ok:
            return
        blocked.add((chat_id, bot_id))      # 记下来，这次运行里不再反复试
        print(f"【飞书】「{name}」用自己的账号发不进这个会话（{why}），改由主账号代发。把它的机器人加进这个群就可以了")
    send(chat_id, f"【{name}】{text}")


def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    """飞书推来一条消息。这里要在 3 秒内结束，所以只检查、排队，不调模型。"""
    message = data.event.message
    sender = data.event.sender
    guest = None                                # 主人发的是 None；访客发的是他的档案
    if sender.sender_id.open_id != FEISHU_OWNER_ID:
        guest = guest_of(message.chat_id, sender.sender_id.open_id)
        if guest is None:
            print("【飞书】忽略了一条不是主人、也不是访客发的消息")
            return
    if message.message_id in seen:
        return
    seen.add(message.message_id)
    if message.message_type != "text":
        if guest is None:                       # 访客发图片、表情不用提醒，免得打扰群里的人聊天
            inbox.put((message.chat_id, None, None, []))
        return
    text = json.loads(message.content)["text"]
    # 在群里 @ 了谁，飞书给的文字里是 @_user_1 这样的记号，这里换回 @名字，后面才认得出点了谁的名
    mentioned = []                              # 这句话 @ 到的人：(名字, 他的编号)。/guest 命令靠它知道请的是谁
    for mention in getattr(message, "mentions", None) or []:
        text = text.replace(mention.key, f"@{mention.name}")
        open_id = getattr(getattr(mention, "id", None), "open_id", None)
        if open_id and getattr(mention, "mentioned_type", "") != "bot":
            mentioned.append((mention.name, open_id))
    clean = MENTION.sub("", text).strip()
    is_stop = guest is None and clean == "/stop"
    if is_stop:
        stop_requests.add(message.chat_id)      # 不排队，马上记下：正在进行的讨论看到就停
    box = pending.get(message.chat_id) if guest is None else None
    if box is not None:                         # 这个会话正等着主人审批：这句话就是他的回答
        box.put(clean)
        if not is_stop:
            return                              # 回答不当成新消息；/stop 既算拒绝，也照常去喊停
    inbox.put((message.chat_id, text, guest, mentioned))


def guest_of(chat_id, open_id):
    """这个人是不是这个会话的访客。是就返回他的档案（字典），不是返回 None。"""
    try:
        guests = list_guests(f"feishu:{chat_id}")
    except Exception as exc:
        print(f"【警告】访客名单读不出来（{type(exc).__name__}），这条消息当作陌生人的")
        return None
    for guest in guests:
        if guest["contact"] == open_id:
            return guest
    return None


def guest_command(chat_id, text, mentioned):
    """管访客的命令：/guest 看名单，/guest @某人 请他当访客，/unguest 名字 请他离开。

    返回 (要显示的话, 名单变没变)；不是这几个命令返回 None。
    """
    command, _, arg = text.partition(" ")
    if command not in ("/guest", "/guests", "/unguest"):
        return None
    session = f"feishu:{chat_id}"
    guests = list_guests(session)
    arg = arg.strip().lstrip("@").strip()

    if command == "/unguest":
        ids = {open_id for name, open_id in mentioned}
        leaving = [guest for guest in guests if guest["name"] == arg or guest["contact"] in ids]
        if not leaving:
            return "这个会话里没有这位访客。看名单：/guest", False
        for guest in leaving:
            remove_guest(session, guest["id"])
        names = "、".join(guest["name"] for guest in leaving)
        return f"「{names}」不再是访客了，Agent 不会再理他的话。关于他的记忆文件还留着。", True

    if not arg:
        if not guests:
            return "这个会话还没有访客。请人：先输入 /guest，空一格，再输入 @ 从列表里选他。", False
        lines = ["这个会话的访客："]
        for guest in guests:
            lines.append(f"- {guest['name']}（关于他的记忆在 guests/{guest['id']}/）")
        lines.append("请人：/guest @名字    请他离开：/unguest 名字")
        return "\n".join(lines), False

    bot_names = {bot.name for bot in all_bots()}
    people = [(name, open_id) for name, open_id in mentioned if open_id != FEISHU_OWNER_ID and name not in bot_names]
    if not people:
        return "要 @ 到那个人才行：先输入 /guest，空一格，再输入 @ 从列表里选他。Agent 不用请，用 /join。", False
    added = [invite_guest(session, "feishu", open_id, name) for name, open_id in people]
    names = "、".join(guest["name"] for guest in added)
    return (
        f"「{names}」现在是这个会话的访客。他说的话 Agent 都能看到，可以直接聊，不用 @；"
        "他可以让 Agent 干活，包括改文件、发通知；关于他的事记在他自己的文件夹里。"
        "他不能用命令。"
        "请他离开：/unguest 名字"
    ), True


def forget(chat_id):
    """这个会话的访客变了：提示词里的访客名单要跟着变，所以丢掉它现在的对话（包括单独对话的），下一句话重新开始。"""
    rooms.pop(chat_id, None)
    for key in [key for key in solo if key[0] == chat_id]:
        del solo[key]


def members_of(chat_id):
    """这个会话的成员名单。存在数据库里，重启也记得；没设置过就只有主 bot。"""
    return list_members(f"feishu:{chat_id}") or ["main"]


def make_member(bot_id, names, guests):
    """给一个 Agent 造工牌、拼提示词、算工具。names 是会话里所有成员的名字，多于一个时加上多人规则；
    guests 是这个会话的访客，有访客时加上访客规则和关于他们的记忆。"""
    ctx = ctx_for(bot_id)
    name = get_agent_name(ctx)
    system = assemble_prompt(ctx) + FEISHU_RULE
    if len(names) > 1:
        system += group_rule(name, names)
    if guests:
        system += guest_rule(guests, alone=len(names) == 1)
    return Member(ctx=ctx, name=name, system=system, tools=tools_for(ctx))


def open_room(chat_id):
    """取出这个会话的 Room。第一次用到，或者成员、访客、能力变过以后，重新建一个。"""
    if chat_id not in rooms:
        ids = members_of(chat_id)
        guests = list_guests(f"feishu:{chat_id}")
        if len(ids) == 1:
            key = (chat_id, ids[0])
            if key not in solo:
                solo[key] = make_member(ids[0], [ids[0]], guests)
            members = [solo[key]]
        else:
            names = [get_agent_name(ctx_for(bot_id)) for bot_id in ids]
            members = [make_member(bot_id, names, guests) for bot_id in ids]
        rooms[chat_id] = Room(members)
    return rooms[chat_id]


def run(member, content, chat_id, guest_id="", note=None):
    """让一个成员看 content，返回它说的话；它决定不接话时返回 None。

    note 不是空的时候，每日记录里用它代替 content（开场指令很长，记一句"它先开口"就够了）。

    guest_id 不是空的，表示这一轮是访客引起的：给它一张标了"访客在说话"的工牌，
    门禁看到这个标记，就不让工具碰别的访客的文件夹，也不让用允许名单以外的工具。
    """
    ctx = replace(member.ctx, guest=guest_id) if guest_id else member.ctx
    messages = trim_messages(member.messages)
    member.messages = messages
    before = len(messages)
    messages.append({"role": "user", "content": content})
    try:
        reply = run_agent(ctx, member.system, member.tools, messages, approver=make_approver(chat_id, member.name))
    except anthropic.APIError:
        del messages[before:]      # 这一轮没做成，从历史里拿掉，下次重新来
        raise
    if reply.strip().startswith(NO_REPLY):
        write_daily(member.ctx, note or content, "（没有回复）")
        return None
    write_daily(member.ctx, note or content, reply)
    return reply


def speak(chat_id, member, reply):
    """把一个成员说的话发到飞书里。"""
    print(f"回复（飞书）：【{member.name}】{reply}")
    send_as(chat_id, member.ctx.bot_id, member.name, reply)


def welcome(chat_id, newcomers):
    """刚加入这个会话、而且一句话都没说过的 Agent，让它们先开口打招呼。newcomers 是它们的编号。"""
    room = open_room(chat_id)
    for member in room.members:
        if member.ctx.bot_id not in newcomers:
            continue
        try:
            room.greet(
                member, OPENING,
                lambda who, content: run(who, content, chat_id, note=OPENING_NOTE),
                lambda who, reply: speak(chat_id, who, reply),
            )
        except anthropic.APIError as exc:
            print(f"【系统】模型接口异常：{type(exc).__name__}")
            send(chat_id, f"「{member.name}」的招呼没发出来（模型接口出错）。直接和它说话就行。")
    backup_workspace("飞书对话后自动备份")


def handle(chat_id, text, guest=None, mentioned=()):
    """处理一条消息。成员们的回复在这里面直接发出去；返回值是另外要告诉用户的一句话，没有就是 None。

    guest 是 None 表示这句话是主人说的；访客说的就是他的档案。mentioned 是这句话 @ 到的人。
    """
    clean = MENTION.sub("", text).strip()
    if guest is not None and clean.startswith("/"):
        return "命令只有主人能用。"
    if clean == "/stop":
        stop_requests.discard(chat_id)
        return "已经停下了。"
    if chat_id in stop_requests:           # 这条消息排在 /stop 前面，一起作废
        print("【飞书】用户喊了停，这条不处理")
        return None

    # 命令只有主人能用。管访客的命令在这个文件里（要用到飞书里 @ 的那个人）
    result = guest_command(chat_id, clean, mentioned) if guest is None else None
    if result is not None:
        reply, changed = result
        if changed:
            forget(chat_id)                # 访客变了，提示词里的访客名单也要变，这个会话重新开始
        return reply

    # 管理 Agent 的命令由 agents/bots 处理；别的话返回 None，交给成员们
    ids = members_of(chat_id)
    result = handle_session_command(clean, ids) if guest is None else None
    if result is not None:
        reply, new_ids, changed = result
        if new_ids != ids:
            set_members(f"feishu:{chat_id}", "feishu", new_ids)
            rooms.pop(chat_id, None)       # 成员变了，这个会话重新开始
        if changed:                        # 有 Agent 的能力变了，所有会话里和它的旧对话都不能接着用
            rooms.clear()
            for key in [key for key in solo if key[1] in changed]:
                del solo[key]
        # 新加入的成员里，一句话都没说过的（刚新建的）先开口打招呼
        newcomers = [bot_id for bot_id in new_ids if bot_id not in ids and is_fresh(ctx_for(bot_id))]
        if not newcomers:
            return reply
        print("回复（飞书）：", reply)
        send(chat_id, reply)               # 先把命令的结果发出去，再让新成员说话
        welcome(chat_id, newcomers)
        return None

    def emit(member, reply):
        speak(chat_id, member, reply)

    room = open_room(chat_id)
    stopped = lambda: chat_id in stop_requests
    try:
        if guest is None:
            notice = room.discuss(text, lambda member, content: run(member, content, chat_id), emit, stopped)
        else:
            # 访客的话：标上【访客·名字】，和主人的话一样交给成员们；工牌上标着是他在说话
            notice = room.discuss(
                text, lambda member, content: run(member, content, chat_id, guest["id"]), emit, stopped,
                speaker=guest_label(guest["name"]),
            )
    except anthropic.APIError as exc:
        print(f"【系统】模型接口异常：{type(exc).__name__}")
        return "模型接口出错了，这条我没处理完。过一会儿再发一次。"
    backup_workspace("飞书对话后自动备份")
    return notice


def worker():
    """一条一条地处理排队的消息。"""
    while True:
        chat_id, text, guest, mentioned = inbox.get()
        if text is None:
            send(chat_id, "我现在只看得懂文字消息。")
            continue
        print(f"访客 {guest['name']}（飞书）：" if guest else "你（飞书）：", text)
        try:
            reply = handle(chat_id, text, guest, mentioned)
        except Exception as exc:
            print(f"【系统】处理消息时出错：{type(exc).__name__}：{exc}")
            reply = "处理这条消息时出错了，回电脑上看一下终端。"
        if reply is None:          # 成员们的话在 handle 里已经发出去了
            continue
        print("回复（飞书）：", reply)
        send(chat_id, reply)


def main():
    global api
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("没有配置：.env 里缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        return
    if not FEISHU_OWNER_ID:
        print("没有配置：.env 里缺少 FEISHU_OWNER_ID。为了安全，不知道主人是谁就不启动")
        return
    ensure_workspace()             # 启动时把工作区准备好；每个 Agent 的提示词等用到它时再拼
    backup_workspace("启动时备份")
    api = lark.Client.builder().app_id(FEISHU_APP_ID).app_secret(FEISHU_APP_SECRET).build()
    threading.Thread(target=worker, daemon=True).start()
    handler = (
        lark.EventDispatcherHandler.builder("", "")
        .register_p2_im_message_receive_v1(on_message)
        .build()
    )
    client = lark.ws.Client(
        FEISHU_APP_ID,
        FEISHU_APP_SECRET,
        event_handler=handler,
        log_level=lark.LogLevel.INFO,
    )
    print("正在连接飞书。连上后在飞书里和它说话，按 Ctrl+C 退出。")
    client.start()


if __name__ == "__main__":
    main()
