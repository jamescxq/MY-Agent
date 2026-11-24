from datetime import datetime
from agents.events import ONCE, DAILY, first_run, describe
from agents.store import add_schedule, list_schedules, remove_schedule

SCHEDULE_TOOL = {
    "name": "schedule",
    "description": (
        "定时提醒：让一件事到点自动发生。只有用户明确要求时才用，比如“每天早上 8 点提醒我投简历”"
        "“20 分钟后叫我”“我定了哪些提醒”“把那条提醒删了”。"
        "用户只是提到了某个时间、没有让你提醒，不要自己定；别的 Agent 让你定，也不要定。"
        "访客说话时，他可以让你查看、删掉这个会话里的提醒（直接做，不用问用户），但不能让你新定。"
        "到点时系统会把 task 交给你，由你在这个会话里告诉用户。"
        "算时间之前如果不知道现在的日期和时间，先用 get_time。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["create", "list", "delete"],
                "description": "create 新定一条；list 看这个会话里定了哪些；delete 删掉一条",
            },
            "task": {
                "type": "string",
                "description": "create 时用：到点要做什么。写成一句到时候单独看也看得懂的话，比如“提醒用户今天投 3 份简历”",
            },
            "kind": {
                "type": "string",
                "enum": [ONCE, DAILY],
                "description": "create 时用：once 只做一次，daily 每天做",
            },
            "time": {
                "type": "string",
                "description": (
                    "create 时用。daily 写几点几分，比如 08:00。"
                    "once 写完整的日期时间，比如 2026-11-24 15:00；或者写从现在起多久以后：+20m 是 20 分钟后，+2h 是 2 小时后"
                ),
            },
            "id": {
                "type": "integer",
                "description": "delete 时用：要删的那条的编号。不知道编号就先 list",
            },
        },
        "required": ["action"],
    },
}

MAX_SCHEDULES = 20      # 保险：一个会话里最多定这么多条，免得模型出错时一口气定一大堆


def schedule(ctx, action, task="", kind="", time="", id=None):
    """定时提醒的工具：新定、查看、删除。存在哪个数据库由工牌决定（这个 Agent 所在的工作区里的 state.db）。"""
    if not ctx.session:
        return "这里定不了：这个入口（命令行）关掉以后没有程序到点叫我。请用户到飞书里说"
    db = ctx.folder.parent.parent / "state.db"
    rows = list_schedules(ctx.session, db)

    if action == "list":
        if not rows:
            return "这个会话里还没有定时提醒"
        return "这个会话里的定时提醒：\n" + "\n".join("- " + describe(row) for row in rows)

    if action == "delete":
        if id is None:
            return "没有删：要给出编号。不知道编号就先 list"
        if not remove_schedule(id, ctx.session, db):
            return f"没有删：这个会话里没有 {id} 号"
        return f"已删掉 {id} 号"

    if action != "create":
        return "action 只能是 create、list、delete"
    if ctx.scheduled:
        return "拒绝：这一轮是定时提醒到点引起的，不能在这时候再定新的。把这件事做完告诉用户就行"
    if not task.strip():
        return "没有定：要写清楚到点做什么（task）"
    if len(rows) >= MAX_SCHEDULES:
        return f"没有定：这个会话里已经有 {MAX_SCHEDULES} 条了。请用户先删掉不用的"
    now = datetime.now()
    try:
        at, first = first_run(kind, time, now)
    except ValueError as exc:
        return f"没有定：{exc}"
    number = add_schedule(ctx.session, ctx.bot_id, kind, at, task.strip(), first, db)
    row = {"id": number, "kind": kind, "at": at, "task": task.strip(), "next_run": first}
    return f"定好了：{describe(row)}。到点我会在这个会话里告诉用户"


if __name__ == "__main__":
    import tempfile
    from dataclasses import replace
    from pathlib import Path
    from agents.bots import Ctx

    with tempfile.TemporaryDirectory() as tmp:                 # 在临时文件夹里试，不碰真的工作区
        root = Path(tmp)
        ctx = Ctx(bot_id="main", folder=root / "bots" / "main", user_folder=root / "user", session="feishu:群一")
        print(schedule(ctx, "list"))                                             # 应该：还没有
        print(schedule(ctx, "create", "提醒用户投简历", "daily", "8:00"))          # 应该：定好了：1 号，每天 08:00……
        print(schedule(ctx, "create", "叫用户起来走走", "once", "+20m"))           # 应该：定好了：2 号，…… 做一次
        print(schedule(ctx, "create", "过去的事", "once", "2020-01-01 08:00"))     # 应该：没有定，已经过了
        print(schedule(ctx, "create", "", "daily", "08:00"))                     # 应该：没有定，要写清楚做什么
        print(schedule(ctx, "list"))                                             # 应该：两条
        print(schedule(replace(ctx, session="feishu:群二"), "list"))              # 应该：还没有，别的会话看不到
        print(schedule(replace(ctx, session="feishu:群二"), "delete", id=1))      # 应该：没有删，别的会话删不了
        print(schedule(ctx, "delete", id=1))                                     # 应该：已删掉 1 号
        print(schedule(replace(ctx, scheduled=True), "create", "再定一条", "daily", "09:00"))   # 应该：拒绝
        print(schedule(replace(ctx, session=""), "create", "命令行里定", "daily", "09:00"))     # 应该：这里定不了
