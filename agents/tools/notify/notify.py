import json
import urllib.request
from config import FEISHU_WEBHOOK

NOTIFY_TOOL = {
    "name": "notify",
    "description": "给用户的飞书发一条通知。后台任务做完了、或者卡住需要用户来处理时调用；用户明确要求发通知时也可以用。平时对话不要用。",
    "input_schema": {
        "type": "object",
        "properties": {
            "text": {
                "type": "string",
                "description": "通知内容。说清楚是哪件事、结果怎样、需不需要用户做什么",
            },
        },
        "required": ["text"],
    },
}

# 发到哪里由 .env 里的地址决定，模型只能决定发什么。
# 飞书的消息格式暂时写在这里；阶段 I 有了连接器以后，搬到 MY-Agent-connectors。
# 这个工具用不到 ctx，但每个工具的第一个参数都统一是它
def notify(ctx, text):
    if not FEISHU_WEBHOOK:
        return "没有配置飞书通知：.env 里缺少 FEISHU_WEBHOOK"
    message = {"msg_type": "text", "content": {"text": "【小牛】" + text}}
    body = json.dumps(message).encode("utf-8")
    request = urllib.request.Request(
        FEISHU_WEBHOOK,
        data=body,
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(request, timeout=10) as response:
        answer = json.loads(response.read().decode("utf-8"))
    if answer.get("code") != 0:
        return f"飞书没有收下这条通知：{answer.get('msg')}"
    return "已发到飞书"

if __name__ == "__main__":
    from agents.bots import main_ctx

    print(notify(main_ctx(), "这是一条测试通知"))
