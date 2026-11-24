import json
from datetime import date
from config import LOGS

# 时钟记数：每天"看了几次有没有到点的事"，其中几次真的有事。
# 用来回答"空转花不花钱"：看了 N 次、有事 M 次，那 N-M 次就是空转，空转的时候代码不调模型。
# 一天只占一行，所以不像 trace.jsonl 那样一次记一行，而是每次把当天的数加一再写回去。
# 文件是 MY-Agent-logs/ticks.json，长这样：{"2026-11-24": {"ticks": 1440, "due": 3}}


def read_ticks(folder=LOGS):
    """读出全部记数。文件不存在或者坏了，当成还没记过。"""
    path = folder / "ticks.json"
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def count_tick(due, folder=LOGS):
    """记一次：时钟响了一下，这一下有 due 件事到点（0 就是空转）。"""
    counts = read_ticks(folder)
    today = counts.setdefault(date.today().isoformat(), {"ticks": 0, "due": 0})
    today["ticks"] += 1
    if due:
        today["due"] += 1
    try:
        folder.mkdir(exist_ok=True)
        (folder / "ticks.json").write_text(json.dumps(counts, ensure_ascii=False, indent=1), encoding="utf-8")
    except OSError as exc:
        print(f"【警告】时钟记数写入失败：{exc}")


def ticks_text(day=None, folder=LOGS):
    """把记数写成一句话。day 写成 "2026-11-24" 只看那一天，不写就把所有天加起来。"""
    counts = read_ticks(folder)
    days = [counts[day]] if day in counts else ([] if day else list(counts.values()))
    ticks = sum(one["ticks"] for one in days)
    due = sum(one["due"] for one in days)
    if not ticks:
        return "  定时检查：没有记录"
    return f"  定时检查：看了 {ticks} 次，{due} 次有到点的事，{ticks - due} 次空转（空转不调模型）"


if __name__ == "__main__":
    import tempfile
    from pathlib import Path

    with tempfile.TemporaryDirectory() as tmp:          # 临时文件夹，假数字不进真的记录
        folder = Path(tmp)
        print(ticks_text(folder=folder))                # 应该：没有记录
        for due in (0, 0, 2, 0):
            count_tick(due, folder)
        print(read_ticks(folder))                       # 应该：今天 {'ticks': 4, 'due': 1}
        print(ticks_text(folder=folder))                # 应该：看了 4 次，1 次有到点的事，3 次空转
        print(ticks_text("2020-01-01", folder))         # 应该：没有记录
