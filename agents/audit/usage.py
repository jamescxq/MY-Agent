# 用量汇总：把 trace.jsonl 里一行一行的记录加起来，变成能看的数字。
# trace.py 管"写"，这里管"读和算"。
#   python -m agents.audit.usage               看今天的和全部的
#   python -m agents.audit.usage 2026-11-24    只看这一天的
# 只读文件，不调模型，不花钱。
import json
import sys
from datetime import date
from config import LOGS


def read_rows(folder=LOGS, day=None):
    """读出用量记录，一行是一个字典。day 写成 "2026-11-24" 就只要那一天的。"""
    path = folder / "trace.jsonl"
    if not path.is_file():
        return []
    rows = []
    for line in path.read_text(encoding="utf-8").splitlines():
        try:
            row = json.loads(line)
        except ValueError:              # 空行，或者写到一半断掉的行：跳过，不让一行坏的毁掉全部
            continue
        if day is None or row["time"].startswith(day):
            rows.append(row)
    return rows


def summarize(rows):
    """按 Agent 把记录加起来。返回 {编号: {几轮, 调了几次, 发了多少, 回了多少, 一共几秒, 最慢几秒}}。

    "一轮"是 run_agent 跑一遍：这个 Agent 被叫到一次。一轮里可能调好几次模型（用了工具就会多调）。
    每一轮的第一次调用 step 都是 1，所以数 step 是 1 的行就知道有几轮。
    """
    result = {}
    for row in rows:
        one = result.setdefault(row["bot"], {"turns": 0, "calls": 0, "input": 0, "output": 0, "seconds": 0.0, "slowest": 0.0})
        one["calls"] += 1
        if row["step"] == 1:
            one["turns"] += 1
        one["input"] += row["input_tokens"]
        one["output"] += row["output_tokens"]
        one["seconds"] += row["seconds"]
        one["slowest"] = max(one["slowest"], row["seconds"])
    return result


def report(rows):
    """把汇总写成几行文字，一个 Agent 一行。"""
    if not rows:
        return "  （没有记录）"
    lines = []
    for bot, one in summarize(rows).items():
        lines.append(
            f"  {bot}：{one['turns']} 轮，调模型 {one['calls']} 次（平均每轮 {one['calls'] / max(one['turns'], 1):.1f} 次）；"
            f"发 {one['input']}、回 {one['output']} 个 token（平均每次发 {one['input'] // one['calls']}）；"
            f"平均每次 {one['seconds'] / one['calls']:.2f} 秒，最慢 {one['slowest']:.2f} 秒"
        )
    return "\n".join(lines)


if __name__ == "__main__":
    from agents.audit.ticks import ticks_text

    if len(sys.argv) > 1:
        print(f"{sys.argv[1]}：")
        print(report(read_rows(day=sys.argv[1])))
        print(ticks_text(sys.argv[1]))
    else:
        today = date.today().isoformat()
        print(f"今天（{today}）：")
        print(report(read_rows(day=today)))
        print(ticks_text(today))
        print("全部：")
        print(report(read_rows()))
        print(ticks_text())
