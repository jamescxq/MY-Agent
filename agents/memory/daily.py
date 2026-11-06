from datetime import datetime
from config import  WORKSPACE

def write_daily(user_input, reply):
    now = datetime.now()
    folder = WORKSPACE / "memory"
    path = folder / f"{now.strftime('%Y-%m-%d')}.md"
    text = f"## {now.strftime('%H:%M')}\n\n**用户**：{user_input}\n\n**助手**：{reply}\n\n"
    try:
        folder.mkdir(exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError as exc:
        print(f"【警告】对话记录写入失败：{exc}")