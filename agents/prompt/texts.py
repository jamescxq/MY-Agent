import re
from config import TEMPLATES

# 写给模型看的整段话，都放在 templates/prompts/ 里，一段一个 .md 文件。
# 代码里不再写大段的提示词，用到的时候从这里读。想改措辞，改那个文件夹里的文件就行，不用动代码。
#
# 现在有这几段（文件名 → 用在哪）：
#   feishu         "你现在在飞书里"的规则，拼在提示词后面          feishu_bot.py
#   opening        新 Agent 第一次对话时的开场指令                 agents/bots/greeting.py
#   opening_main   主 bot 第一次启动时的开场指令                   agents/bots/greeting.py
#   persona        新建 Agent 时，让模型起草人设的说明             agents/bots/persona.py
#   group          "这个会话里有多个 Agent"的规则                  agents/sessions/discussion.py
#   guest          "这个会话里有访客"的规则                        agents/sessions/guests.py
#   due            定时提醒到点时，代码替用户说的那句话             agents/events/scheduler.py
#
# 不放在这里的：工具自己的说明（和工具的参数写在一起）、代码现算出来的清单（比如能力清单）、
# 程序回给用户看的话（比如"已新建……"）。

PROMPTS_DIR = TEMPLATES / "prompts"


def prompt_text(file, /, **values):
    """读出 templates/prompts/<file>.md 里的那段话。

    话里有 {task} 这样的空，就用同名的值填上，比如 prompt_text("due", task="提醒投简历")。
    给了值、文件里却没有对应的空，会报错：说明文件和代码对不上了，早点发现比悄悄漏掉好。

    参数表里的 / 表示：第一个参数只能按位置传，不能写成 file=...。
    这样文件里要填的空叫什么名字都行（哪怕也叫 file），不会和它撞上。
    """
    text = (PROMPTS_DIR / f"{file}.md").read_text(encoding="utf-8").strip("\n")
    for key in values:
        if "{" + key + "}" not in text:
            raise ValueError(f"templates/prompts/{file}.md 里没有 {{{key}}} 这个空")
    # 一次把所有的空填完。不认识的 {xxx} 原样留着（有的话里本来就有花括号）
    return re.sub(r"\{(\w+)\}", lambda found: str(values.get(found.group(1), found.group(0))), text)


if __name__ == "__main__":
    for path in sorted(PROMPTS_DIR.glob("*.md")):
        text = path.read_text(encoding="utf-8")
        print(path.stem, "：", len(text), "个字，要填的空：", sorted(set(re.findall(r"\{(\w+)\}", text))))
    print(prompt_text("due", task="提醒用户投简历").splitlines()[1])     # 应该：到点要做的事：提醒用户投简历
    try:
        prompt_text("due", who="x")
    except ValueError as exc:
        print("拒绝：", exc)                                           # 应该：拒绝，没有 {who} 这个空
