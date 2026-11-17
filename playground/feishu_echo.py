# 试验脚本：和飞书建立长连接，收到消息就打印出来。不回复，也不调用模型。
# 运行：python -m playground.feishu_echo
import json
import lark_oapi as lark
from config import FEISHU_APP_ID, FEISHU_APP_SECRET


def on_message(data: lark.im.v1.P2ImMessageReceiveV1) -> None:
    message = data.event.message
    sender = data.event.sender
    print("【收到消息】")
    print("  谁发的:", sender.sender_id.open_id, "| 类型:", sender.sender_type)
    print("  哪个会话:", message.chat_id, "| 群聊还是私聊:", message.chat_type)
    if message.message_type == "text":
        print("  内容:", json.loads(message.content)["text"])
    else:
        print("  内容: （不是文字，类型是", message.message_type, "）")


handler = (
    lark.EventDispatcherHandler.builder("", "")
    .register_p2_im_message_receive_v1(on_message)
    .build()
)

if __name__ == "__main__":
    if not FEISHU_APP_ID or not FEISHU_APP_SECRET:
        print("没有配置：.env 里缺少 FEISHU_APP_ID 或 FEISHU_APP_SECRET")
    else:
        client = lark.ws.Client(
            FEISHU_APP_ID,
            FEISHU_APP_SECRET,
            event_handler=handler,
            log_level=lark.LogLevel.INFO,
        )
        print("正在连接飞书，连上后在群里发消息试试。按 Ctrl+C 退出。")
        client.start()
