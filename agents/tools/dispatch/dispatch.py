from dataclasses import replace
from config import TEMPLATES

# 派单：把一件重活交给一个"子智能体"去做，等它做完，只拿回它最后那段汇报。
#
# 子智能体不是另一种东西，就是把 run_agent 那个循环再跑一遍，只是换了三样：
#   1. 对话是全新的：它看不到派它的 Agent 和用户聊过什么，只看到交代给它的任务和背景。
#   2. 提示词是 templates/workers/general.md，不是那个 Agent 的人设。
#   3. 工具只有"查"的那几个（见下面的 WORKER_TOOLS），而且派它的 Agent 有哪些它才有哪些。
#
# 这样做的好处：它中间搜回来的几万个 token 都留在它自己那段对话里，回到派它的 Agent 手里的只有汇报。
# 代价：它要带着自己的提示词从头开始，每派一次至少多调一次模型。所以简单的事不该派。

DISPATCH_TOOL = {
    "name": "dispatch",
    "description": (
        "把一件独立的重活派给一个子智能体去做。你等它做完，拿回一段汇报。"
        "适合：要搜好几次、读好几个网页或文件才能回答的事，比如“查一下某公司实习岗位的要求”。"
        "不适合：一两步就能做完的事，自己做更快也更省。"
        "子智能体是一个全新的助手：它看不到你和用户的对话，不知道用户是谁，做的中间也没法问你。"
        "所以 task 要写成一句完整的交代，context 里写上它需要知道、又没法自己查到的一切。"
        "它只能查不能改：能看时间、读文件、搜索、读网页（你有哪些它才有哪些），不能写文件、发通知、定提醒。"
        "要留下东西的事，等它回来以后你自己做。"
        "它的汇报用户看不到。你读完以后，用自己的话把要紧的告诉用户，并带上来源。"
        "一次只交代一件事。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "task": {
                "type": "string",
                "description": "要它做的事，写成一句完整的交代。看的人没见过之前的对话，所以不要写“刚才说的那家”这种话",
            },
            "context": {
                "type": "string",
                "description": "背景：它需要知道、又没法自己查到的事。比如用户关心什么、要哪种格式、已经知道哪些、文件在哪个路径。没有就写“无”",
            },
        },
        "required": ["task", "context"],
    },
}

# 子智能体能用的工具。用"允许名单"：以后新加的工具，子智能体默认没有，要给它用就加到这里。
# 现在全是只读的，所以它不会改任何东西，也就不需要问用户同不同意。
WORKER_TOOLS = ("get_time", "read_file", "list_file", "web_search", "web_fetch")
MAX_REPORT = 8000       # 汇报最多带回多少个字，超过的截掉。免得一份很长的汇报又把派它的 Agent 的对话塞满


def refuse(name, args, reason=""):
    """子智能体的审批函数：一律不同意。它没有要审批的工具，走到这里说明哪里漏了，拦住最稳妥。"""
    return False


def dispatch(ctx, task, context=""):
    """派一个子智能体去做 task，返回它的汇报。ctx 是派它的那个 Agent 的工牌。"""
    # 放在函数里面 import：agents.loop 会用到工具清单，工具清单里有这个工具，
    # 写在文件最上面的话它们会互相等对方先加载完。
    from agents.loop import run_agent, OUT_OF_STEPS
    from agents.capabilities import tools_for
    from agents.permission.taint import has_outside, mark_outside

    task = (task or "").strip()
    if not task:
        return "没有派出去：task 是空的。写清楚要它做什么"

    system = (TEMPLATES / "workers" / "general.md").read_text(encoding="utf-8").strip()
    tools = [tool for tool in tools_for(ctx) if tool["name"] in WORKER_TOOLS]
    messages = [{"role": "user", "content": f"要做的事：{task}\n\n背景：{(context or '').strip() or '无'}"}]
    worker = replace(ctx, worker=True)      # 同一张工牌，只多标一个"我是子智能体"：读文件的范围和派它的 Agent 一样

    print(f"【派单】{ctx.bot_id} 派了一个子智能体：{task[:60]}")
    report = run_agent(worker, system, tools, messages, approver=refuse)
    if report == OUT_OF_STEPS:
        return "子智能体没做完：步数用完了。把这件事拆小一点再派，或者自己做"
    if not report.strip():
        return "子智能体什么都没汇报。可以换个说法再派一次，或者自己做"
    if len(report) > MAX_REPORT:
        report = report[:MAX_REPORT] + f"\n（汇报太长，只带回了前 {MAX_REPORT} 个字）"
    if has_outside(messages):
        # 它读过网页或搜索结果：汇报里可能带着网页里的话，包上"这是外面来的内容"的说明再交回去
        return mark_outside("子智能体查资料后写的汇报", report)
    return "子智能体的汇报：\n" + report


if __name__ == "__main__":
    print(DISPATCH_TOOL["name"], WORKER_TOOLS)
    print(dispatch(None, "  "))             # 应该：没有派出去，task 是空的（这一步不调模型）
