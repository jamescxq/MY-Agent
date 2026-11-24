import json
from datetime import datetime
from config import LOGS

# 用量记录：每调一次模型记一行。和 audit.py 是一个写法，记的东西不一样：
# audit.py 记"用了哪个工具、有没有经过同意"，这里记"谁调的、花了多少 token、用了几秒"。
# folder 平时不用传，记在日志文件夹里；自测时传一个临时文件夹，免得假数字混进真记录。
def write_trace(bot, step, input_tokens, output_tokens, seconds, folder=LOGS):
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "bot": bot,
        "step": step,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "seconds": round(seconds, 2),
    }
    line = json.dumps(record, ensure_ascii=False)
    try:
        folder.mkdir(exist_ok=True)
        with open(folder / "trace.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as exc:
        print(f"【警告】用量记录写入失败：{exc}")

if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    with tempfile.TemporaryDirectory() as tmp:
        write_trace("main", 1, 5286, 19, 2.5, folder=Path(tmp))
        write_trace("bot-1", 2, 6100, 240, 7.126, folder=Path(tmp))
        print((Path(tmp) / "trace.jsonl").read_text(encoding="utf-8"))
