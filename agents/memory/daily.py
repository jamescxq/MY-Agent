from datetime import datetime

def write_daily(ctx, user_input, reply):
    """把这一轮对话追加到这个 Agent 自己的每日记录里：它的文件夹/memory/日期.md"""
    now = datetime.now()
    folder = ctx.folder / "memory"
    path = folder / f"{now.strftime('%Y-%m-%d')}.md"
    text = f"## {now.strftime('%H:%M')}\n\n**用户**：{user_input}\n\n**助手**：{reply}\n\n"
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as f:
            f.write(text)
    except OSError as exc:
        print(f"【警告】对话记录写入失败：{exc}")
