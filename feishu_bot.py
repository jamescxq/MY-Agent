# 入口：飞书。你在飞书里发的消息交给小牛，它的回复发回飞书。
# 运行：python feishu_bot.py（要一直开着）
# 阶段 I 建了 MY-Agent-connectors 仓库以后，这个文件搬过去。
import json
import queue
import threading

import anthropic
import lark_oapi as lark
from lark_oapi.api.im.v1 import CreateMessageRequest, CreateMessageRequestBody

from config import FEISHU_APP_ID, FEISHU_APP_SECRET, FEISHU_OWNER_ID
from agents.prompt.builder import build_system_prompt, get_agent_name
from agents.loop import run_agent
from agents.tools import TOOLS
from agents.memory import write_daily, backup_workspace
from agents.context import trim_messages

NO_REPLY = "[不回复]"

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
conversations = {}         # 每个会话各自的对话历史
system_prompt = ""         # 启动时生成一次，之后不变
api = None                 # 用来往飞书发消息


def deny(name, args):
    """飞书里没人守着命令行，需要审批的操作一律不同意。"""
    return False


def send(chat_id, text):
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
    response = api.im.v1.message.create(request)
    if not response.success():
        print(f"【飞书】发送失败：{response.code} {response.msg}")


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
    inbox.put((message.chat_id, json.loads(message.content)["text"]))


def handle(chat_id, text):
    """处理一条消息，返回要发回去的话；不需要回复时返回 None。"""
    messages = trim_messages(conversations.get(chat_id, []))
    conversations[chat_id] = messages
    before = len(messages)
    messages.append({"role": "user", "content": text})
    try:
        reply = run_agent(system_prompt, TOOLS, messages, approver=deny)
    except anthropic.APIError as exc:
        del messages[before:]      # 这一轮没做成，从历史里拿掉，下次重新来
        print(f"【系统】模型接口异常：{type(exc).__name__}")
        return "模型接口出错了，这条我没处理。过一会儿再发一次。"
    if reply.strip().startswith(NO_REPLY):
        write_daily(text, "（没有回复）")
        return None
    write_daily(text, reply)
    backup_workspace("飞书对话后自动备份")
    return reply


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
        if reply is None:
            print(f"{get_agent_name()}：（决定不回复）")
            continue
        print(f"{get_agent_name()}：", reply)
        send(chat_id, reply)


def main():
    global system_prompt, api
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("没有配置：.env 里缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
        return
    if not FEISHU_OWNER_ID:
        print("没有配置：.env 里缺少 FEISHU_OWNER_ID。为了安全，不知道主人是谁就不启动")
        return
    system_prompt = build_system_prompt() + FEISHU_RULE
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
