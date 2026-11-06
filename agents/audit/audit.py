import json
from datetime import datetime
from config import LOGS

def write_audit(tool, path, approval, success):
    record = {
        "time": datetime.now().isoformat(timespec="seconds"),
        "tool": tool,
        "path": path,
        "approval": approval,
        "success": success,
    }
    line = json.dumps(record, ensure_ascii=False)
    try:
        LOGS.mkdir(exist_ok=True)
        with open(LOGS / "audit.jsonl", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError as exc:
        print(f"【警告】审计日志写入失败：{exc}")

if __name__ == "__main__":
    write_audit("write_file", "a.md", "同意", True)
    write_audit("read_file", "b.md", "不需要", False)
    print((LOGS / "audit.jsonl").read_text(encoding="utf-8"))