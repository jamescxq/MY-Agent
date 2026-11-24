import re
import threading
import time
from datetime import datetime, timedelta
from agents.prompt.texts import prompt_text
from agents.store import due_schedules, finish_schedule
from agents.audit import count_tick

# 定时提醒里所有入口都一样的部分：
#   - 时间怎么算：第一次什么时候做、做完以后下一次是什么时候
#   - 到点时对 Agent 说什么
#   - 看一眼有没有到点的（run_due）：查数据库、记数、登记做完
#   - 时钟：每隔一会儿叫一次入口
#
# 这个文件不认识飞书，也不调模型。SQL 不写在这里，在 agents/store/schedules.py。
# 到点以后怎么把话送出去，由入口（现在是 feishu_bot.py）给一个函数，传给 run_due。

FORMAT = "%Y-%m-%d %H:%M"          # 时间统一写成这样：2026-11-24 15:00
ONCE = "once"                      # 只做一次
DAILY = "daily"                    # 每天做


def stamp(moment):
    """把一个时间写成 2026-11-24 15:00 这样的文字。"""
    return moment.strftime(FORMAT)


def clock_time(text):
    """把 "8:00"、"08：00" 读成 (8, 0)。读不出来抛 ValueError。"""
    match = re.fullmatch(r"(\d{1,2})[:：](\d{2})", text.strip())
    if not match or int(match.group(1)) > 23 or int(match.group(2)) > 59:
        raise ValueError(f"时间“{text}”看不懂，要写成 08:00 这样")
    return int(match.group(1)), int(match.group(2))


def first_run(kind, when, now):
    """算出第一次该做的时间。返回 (存进数据库的写法, 第一次的时间)，都是文字。

    每天做的（daily）：when 是 "08:00"。今天这个点还没过就是今天，过了就是明天。
    只做一次的（once）：when 可以是 "2026-11-24 15:00"，也可以是 "+20m"（20 分钟后）、"+2h"（2 小时后）。
    说不通的时候抛 ValueError，里面的话是给模型看的，它看了可以改一下再试。
    """
    when = when.strip()
    if kind == DAILY:
        hour, minute = clock_time(when)
        moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
        if moment <= now:
            moment += timedelta(days=1)
        return f"{hour:02d}:{minute:02d}", stamp(moment)
    if kind != ONCE:
        raise ValueError(f"kind 只能是 {ONCE} 或 {DAILY}")

    relative = re.fullmatch(r"\+(\d+)\s*([mh])", when.lower())
    if relative:
        amount = int(relative.group(1))
        if amount == 0:
            raise ValueError("要晚于现在，不能是 +0")
        delta = timedelta(minutes=amount) if relative.group(2) == "m" else timedelta(hours=amount)
        moment = (now + delta).replace(second=0, microsecond=0)
        return stamp(moment), stamp(moment)
    try:
        moment = datetime.strptime(when.replace("：", ":"), FORMAT)
    except ValueError:
        raise ValueError(f"时间“{when}”看不懂。只做一次的要写成 2026-11-24 15:00，或者 +20m、+2h") from None
    if moment <= now:
        raise ValueError(f"{stamp(moment)} 已经过了，现在是 {stamp(now)}")
    return stamp(moment), stamp(moment)


def next_run(kind, at, now):
    """一件事刚做完，它下一次该什么时候做。只做一次的返回 None（表示可以删了）。

    每天做的：下一个还没到的那个点。就算程序关了三天，也只排到下一个，不会把落下的三次都补上。
    """
    if kind != DAILY:
        return None
    hour, minute = clock_time(at)
    moment = now.replace(hour=hour, minute=minute, second=0, microsecond=0)
    if moment <= now:
        moment += timedelta(days=1)
    return stamp(moment)


def describe(row):
    """把一条记录说成一句人话，比如：3 号，每天 08:00：提醒投简历（下一次 2026-11-25 08:00）"""
    if row["kind"] == DAILY:
        return f"{row['id']} 号，每天 {row['at']}：{row['task']}（下一次 {row['next_run']}）"
    return f"{row['id']} 号，{row['at']} 做一次：{row['task']}"


def due_text(task):
    """到点时交给 Agent 的那句话。它是代码替用户说的，所以要讲明白：这不是用户刚说的。

    原文在 templates/prompts/due.md。
    """
    return prompt_text("due", task=task)


def run_due(prefix, deliver, now=None):
    """看一眼有没有到点的定时提醒，有就一条一条交给入口去送。返回这一下有几条到点。

    prefix    只管会话编号是这个开头的。飞书入口传 "feishu:"；别的入口（以后的网页）定的，留给那个入口自己送
    deliver   入口给的函数，deliver(row) 把这一条送出去。怎么送（发飞书、推到网页）是入口的事，这里不管
    now       平时不用传，就是现在；测试时用来假装"现在是几点"

    没有到点的事就什么都不做，不调模型，只记一笔"看了一次"。
    一条提醒不管送没送成都算做过了，不会每分钟重试一遍：只做一次的删掉，每天做的排到下一次。
    """
    now = now or datetime.now()
    due = [row for row in due_schedules(stamp(now)) if row["session_id"].startswith(prefix)]
    count_tick(len(due))
    for row in due:
        try:
            deliver(row)
        except Exception as exc:
            print(f"【系统】定时提醒 {row['id']} 号出错：{type(exc).__name__}：{exc}")
        finish_schedule(row["id"], next_run(row["kind"], row["at"], now))
    return len(due)


def start_clock(on_tick, seconds):
    """开一个后台时钟：先叫一次 on_tick（程序刚启动，把关着的时候落下的补上），之后每隔 seconds 秒叫一次。

    on_tick 里不要干重活。飞书入口传进来的是"往队列里放一个记号"，真正的活由 worker 排着队去做。
    """
    def loop():
        while True:
            try:
                on_tick()
            except Exception as exc:
                print(f"【警告】时钟这一下出错了：{type(exc).__name__}：{exc}")
            time.sleep(seconds)

    thread = threading.Thread(target=loop, daemon=True)
    thread.start()
    return thread


if __name__ == "__main__":
    now = datetime(2026, 11, 24, 14, 30)
    print(first_run(DAILY, "8:00", now))                 # 应该：('08:00', '2026-11-25 08:00')，今天 8 点已经过了
    print(first_run(DAILY, "15：00", now))               # 应该：('15:00', '2026-11-24 15:00')，全角冒号也认
    print(first_run(ONCE, "+20m", now))                  # 应该：('2026-11-24 14:50', '2026-11-24 14:50')
    print(first_run(ONCE, "+2h", now))                   # 应该：('2026-11-24 16:30', '2026-11-24 16:30')
    print(first_run(ONCE, "2026-11-25 09:00", now))      # 应该：('2026-11-25 09:00', '2026-11-25 09:00')
    for kind, when in ((ONCE, "2026-11-24 14:00"), (ONCE, "明天下午"), (DAILY, "25:00"), ("weekly", "08:00")):
        try:
            first_run(kind, when, now)
        except ValueError as exc:
            print("拒绝：", exc)                          # 应该：四个都拒绝
    print(next_run(ONCE, "2026-11-24 15:00", now))       # 应该：None
    print(next_run(DAILY, "08:00", now))                 # 应该：2026-11-25 08:00
    print(next_run(DAILY, "08:00", datetime(2026, 11, 27, 10, 0)))   # 应该：2026-11-28 08:00，落下的不补
    print(describe({"id": 3, "kind": DAILY, "at": "08:00", "task": "提醒投简历", "next_run": "2026-11-25 08:00"}))
    print(due_text("提醒投简历"))
