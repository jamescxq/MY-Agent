# 跑评测：python -m evals.run
#   python -m evals.run              每道题跑 3 次，3 次都对才算通过
#   python -m evals.run --runs 1     每道题只跑 1 次（省钱，改代码时先这样试）
#   python -m evals.run --task 记住称呼    只跑这一道
#
# 注意：会真的调用模型，要花钱。
# 每一次都新建一个临时文件夹当工作区，跑完就删，碰不到真的记忆。
import argparse
import shutil
import sys
import tempfile
from dataclasses import replace
from pathlib import Path

import anthropic

import agents.loop as loop
from config import TEMPLATES
from agents.bots import Ctx
from agents.permission.guard import safe_path
from agents.prompt.builder import assemble_prompt
from agents.tools import TOOL_FUNCTIONS
from agents.capabilities import enabled_ids, tools_for
from agents.sessions import guest_label, guest_rule
from evals.graders import check
from evals.tasks import ALL_TASKS


def make_agent(root, files, is_main=True, packs=()):
    """在临时文件夹 root 里建一个 Agent：先放空白模板，再放这道题的初始文件。返回它的工牌。

    is_main=False 表示它是专属 Agent，不是主 bot：能读公共的 user/，不能改。
    packs 是这道题给它打开的能力包；主 bot 不写就是全开。
    """
    # session 是这道题的"会话编号"：定时提醒的工具要靠它知道记在哪个会话名下
    ctx = Ctx(bot_id="eval", folder=root / "bots" / "eval", user_folder=root / "user", can_write_user=True, session="eval:题目")
    ctx.folder.mkdir(parents=True)
    ctx.user_folder.mkdir(parents=True)
    shutil.copy(TEMPLATES / "bot" / "AGENT.md", ctx.folder / "AGENT.md")
    shutil.copy(TEMPLATES / "bot" / "MEMORY.md", ctx.folder / "MEMORY.md")
    shutil.copy(TEMPLATES / "user" / "USER.md", ctx.user_folder / "USER.md")
    shutil.copy(TEMPLATES / "user" / "MEMORY.md", ctx.user_folder / "MEMORY.md")
    for path, content in files.items():
        target = safe_path(ctx, path, write=True)
        if target is None:
            raise ValueError(f"题目写错了：初始文件 {path} 不在 Agent 能碰到的地方")
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")
    ctx.can_write_user = is_main          # 初始文件放好以后，再按身份收回改 user/ 的权限
    ctx.packs = enabled_ids("main" if is_main else "eval", packs)
    return ctx


USED = []      # 评测里每调一次模型记一行（在 main 里接上）。只在内存里，不写进平时聊天的那份 trace.jsonl


def note_usage(bot, step, input_tokens, output_tokens, seconds):
    """评测时顶替 write_trace：同样的五个数，记进上面的列表。"""
    USED.append({"bot": bot, "step": step, "input_tokens": input_tokens, "output_tokens": output_tokens, "seconds": seconds})


def usage_text(rows, runs=1):
    """把几行用量加起来写成一句话。runs 大于 1 时除以它，得到平均每次的数。"""
    calls = len(rows) / runs
    sent = sum(row["input_tokens"] for row in rows) / runs
    got = sum(row["output_tokens"] for row in rows) / runs
    seconds = sum(row["seconds"] for row in rows) / runs
    return f"调模型 {calls:g} 次，发 {sent:.0f}、回 {got:.0f} 个 token，模型用时 {seconds:.1f} 秒"


def tools_called(messages):
    """从对话历史里找出调用过哪些工具，按顺序。"""
    names = []
    for message in messages:
        if message["role"] != "assistant" or isinstance(message["content"], str):
            continue
        for block in message["content"]:
            if block.type in ("tool_use", "server_tool_use"):      # 后一种是模型那边的服务器替我们执行的（搜索、读网页）
                names.append(block.name)
    return names


def run_once(task):
    """把一道题跑一次。返回 (对不对, 没通过的说明列表, 这次的结果)。"""
    answer = task.get("审批", True)
    start = len(USED)                       # 这一次开始前已经记了几行；后面多出来的就是这一次用的
    with tempfile.TemporaryDirectory() as tmp:
        ctx = make_agent(Path(tmp), task["初始文件"], is_main=task.get("身份") != "专属", packs=task.get("能力包", ()))
        system = assemble_prompt(ctx)
        speaking = ctx                      # 说话时用的工牌。访客说话时换成标了"访客在说话"的那张
        label = ""
        if task.get("访客"):                # 这道题里说话的不是用户，是一位访客
            guest = {"id": "guest-1", "name": task["访客"]}
            ctx.guests_folder = Path(tmp) / "guests"
            (ctx.guests_folder / guest["id"]).mkdir(parents=True)
            shutil.copy(TEMPLATES / "guest" / "MEMORY.md", ctx.guests_folder / guest["id"] / "MEMORY.md")
            system += guest_rule([guest], alone=True, folder=ctx.guests_folder)
            speaking = replace(ctx, guest=guest["id"])
            label = f"【{guest_label(guest['name'])}】"
        messages = []
        reply = ""
        for text in task["用户说"]:
            messages.append({"role": "user", "content": label + text})
            reply = loop.run_agent(speaking, system, tools_for(ctx), messages, approver=lambda name, args, reason="": answer)
        result = {"ctx": ctx, "reply": reply, "tools": tools_called(messages), "usage": USED[start:]}
        problems = []
        for item in task["检查"]:           # 检查要在临时文件夹被删掉之前做
            ok, detail = check(result, item)
            if not ok:
                problems.append(detail)
        return not problems, problems, result


def run_task(task, runs):
    """把一道题跑 runs 次，全对才算通过。"""
    print(f"\n题目：{task['名字']}")
    passed = 0
    finished = 0                # 跑完了几次（通过、不通过都算；接口出错的不算）
    used = []                   # 跑完的这几次一共用了多少
    for i in range(1, runs + 1):
        try:
            ok, problems, result = run_once(task)
        except anthropic.APIError as exc:
            print(f"  第 {i} 次：没跑成，模型接口出错（{type(exc).__name__}）")
            continue
        finished += 1
        used += result["usage"]
        if ok:
            passed += 1
            print(f"  第 {i} 次：通过。调用的工具：{result['tools']}")
        else:
            print(f"  第 {i} 次：不通过。调用的工具：{result['tools']}")
            for detail in problems:
                print(f"      ✗ {detail}")
            print(f"      最后的回复：{result['reply'][:200]}")
        print(f"      用量：{usage_text(result['usage'])}")
    ok = passed == runs
    print(f"  结果：{runs} 次里 {passed} 次通过 → {'通过' if ok else '不通过'}")
    if finished > 1:
        print(f"  平均每次：{usage_text(used, finished)}")
    return ok


def main():
    parser = argparse.ArgumentParser(description="跑评测题（会真的调用模型，要花钱）")
    parser.add_argument("--runs", type=int, default=3, help="每道题跑几次，默认 3")
    parser.add_argument("--task", help="只跑名字是这个的题")
    args = parser.parse_args()

    tasks = [t for t in ALL_TASKS if args.task in (None, t["名字"])]
    if not tasks:
        print(f"没有叫“{args.task}”的题。现有的题：{[t['名字'] for t in ALL_TASKS]}")
        sys.exit(1)

    # 评测里的工具调用不是用户真的在用，不写进真的审计日志
    loop.write_audit = lambda *record: None
    # 用量记录也不写进平时聊天的那份，改成记在上面的 USED 里，跑完报出来
    loop.write_trace = note_usage
    # 评测里不真的往飞书发通知：换成一个只回答"已发送"的假工具
    TOOL_FUNCTIONS["notify"] = lambda ctx, text: "已发送（评测里没有真的发）"

    passed = sum(run_task(task, args.runs) for task in tasks)
    print(f"\n总计：{len(tasks)} 道题，通过 {passed} 道")
    print(f"总用量：{usage_text(USED)}")
    sys.exit(0 if passed == len(tasks) else 1)


if __name__ == "__main__":
    main()
