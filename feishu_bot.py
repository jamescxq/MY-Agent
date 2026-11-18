# 入口：飞书。你在飞书里发的消息交给 Agent，它的回复发回飞书。
# 一个飞书会话（群或单聊）有一份成员名单，默认只有主 bot。
# /bots 看有哪些，/join 名字 让它加入，/leave 名字 让它离开，/use 名字 只留一个，
# /new 名字 新建并加入，/packs 看能力，/stop 让它们停下。
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

import anthropic
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_OWNER_ID, feishu_app
from agents.bots import ctx_for, handle_session_command, ensure_workspace
from agents.prompt.builder import assemble_prompt, get_agent_name
from agents.loop import run_agent
from agents.capabilities import tools_for
from agents.memory import write_daily, backup_workspace
from agents.context import trim_messages
from agents.store import list_members, set_members
from agents.sessions import NO_REPLY, Member, Room, group_rule

FEISHU_RULE = """

## 你现在在飞书里

用户正通过飞书和你对话，不在电脑前。

- 用户发的每一条消息你都能看到，但不是每一条都要回。用户只是随口说一句、自言自语，或者这句话明显不需要你接话时，只输出 [不回复] 这五个字符，不要加任何别的内容。
- 用户在问你、让你做事，或者你有对用户有用的话要说时，正常回复。拿不准就回复。
- 飞书里显示不了表格和标题这类格式，回复用纯文字，尽量短。
- 需要用户审批的操作（比如覆盖已有文件）在这里会被直接拒绝。被拒绝时不要重试，告诉用户这件事要回到电脑的命令行里做。
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


def deny(name, args):
    """飞书里没人守着命令行，需要审批的操作一律不同意。"""
    return False


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
    if sender.sender_id.open_id != FEISHU_OWNER_ID:
        print("【飞书】忽略了一条不是主人发的消息")
        return
    if message.message_id in seen:
        return
    seen.add(message.message_id)
    if message.message_type != "text":
        inbox.put((message.chat_id, None))
        return
    text = json.loads(message.content)["text"]
    # 在群里 @ 了谁，飞书给的文字里是 @_user_1 这样的记号，这里换回 @名字，后面才认得出点了谁的名
    for mention in getattr(message, "mentions", None) or []:
        text = text.replace(mention.key, f"@{mention.name}")
    if MENTION.sub("", text).strip() == "/stop":
        stop_requests.add(message.chat_id)      # 不排队，马上记下：正在进行的讨论看到就停
    inbox.put((message.chat_id, text))


def members_of(chat_id):
    """这个会话的成员名单。存在数据库里，重启也记得；没设置过就只有主 bot。"""
    return list_members(f"feishu:{chat_id}") or ["main"]


def make_member(bot_id, names):
    """给一个 Agent 造工牌、拼提示词、算工具。names 是会话里所有成员的名字，多于一个时加上多人规则。"""
    ctx = ctx_for(bot_id)
    name = get_agent_name(ctx)
    system = assemble_prompt(ctx) + FEISHU_RULE
    if len(names) > 1:
        system += group_rule(name, names)
    return Member(ctx=ctx, name=name, system=system, tools=tools_for(ctx))


def open_room(chat_id):
    """取出这个会话的 Room。第一次用到，或者成员、能力变过以后，重新建一个。"""
    if chat_id not in rooms:
        ids = members_of(chat_id)
        if len(ids) == 1:
            key = (chat_id, ids[0])
            if key not in solo:
                solo[key] = make_member(ids[0], [ids[0]])
            members = [solo[key]]
        else:
            names = [get_agent_name(ctx_for(bot_id)) for bot_id in ids]
            members = [make_member(bot_id, names) for bot_id in ids]
        rooms[chat_id] = Room(members)
    return rooms[chat_id]


def run(member, content):
    """让一个成员看 content，返回它说的话；它决定不接话时返回 None。"""
    messages = trim_messages(member.messages)
    member.messages = messages
    before = len(messages)
    messages.append({"role": "user", "content": content})
    try:
        reply = run_agent(member.ctx, member.system, member.tools, messages, approver=deny)
    except anthropic.APIError:
        del messages[before:]      # 这一轮没做成，从历史里拿掉，下次重新来
        raise
    if reply.strip().startswith(NO_REPLY):
        write_daily(member.ctx, content, "（没有回复）")
        return None
    write_daily(member.ctx, content, reply)
    return reply


def handle(chat_id, text):
    """处理一条消息。成员们的回复在这里面直接发出去；返回值是另外要告诉用户的一句话，没有就是 None。"""
    clean = MENTION.sub("", text).strip()
    if clean == "/stop":
        stop_requests.discard(chat_id)
        return "已经停下了。"
    if chat_id in stop_requests:           # 这条消息排在 /stop 前面，一起作废
        print("【飞书】用户喊了停，这条不处理")
        return None

    # 管理 Agent 的命令由 agents/bots 处理；别的话返回 None，交给成员们
    ids = members_of(chat_id)
    result = handle_session_command(clean, ids)
    if result is not None:
        reply, new_ids, changed = result
        if new_ids != ids:
            set_members(f"feishu:{chat_id}", "feishu", new_ids)
            rooms.pop(chat_id, None)       # 成员变了，这个会话重新开始
        if changed:                        # 有 Agent 的能力变了，所有会话里和它的旧对话都不能接着用
            rooms.clear()
            for key in [key for key in solo if key[1] in changed]:
                del solo[key]
        return reply

    def emit(member, reply):
        print(f"回复（飞书）：【{member.name}】{reply}")
        send_as(chat_id, member.ctx.bot_id, member.name, reply)

    room = open_room(chat_id)
    try:
        notice = room.discuss(text, run, emit, stopped=lambda: chat_id in stop_requests)
    except anthropic.APIError as exc:
        print(f"【系统】模型接口异常：{type(exc).__name__}")
        return "模型接口出错了，这条我没处理完。过一会儿再发一次。"
    backup_workspace("飞书对话后自动备份")
    return notice


def worker():
    """一条一条地处理排队的消息。"""
    while True:
        chat_id, text = inbox.get()
        if text is None:
            send(chat_id, "我现在只看得懂文字消息。")
            continue
        print("你（飞书）：", text)
        try:
            reply = handle(chat_id, text)
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
