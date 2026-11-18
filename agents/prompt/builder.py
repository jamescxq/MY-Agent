from config import TEMPLATES
from agents.bots import ensure_workspace

PLACEHOLDER = "*(在首次对话时填写，可以是用户给你起的名字)*"

def prompt_files(ctx):
    """提示词由哪些文件拼成，按顺序。左边是给模型看的名字（也是工具里用的路径），右边是文件真正的位置。"""
    return [
        ("RULE.md", TEMPLATES / "RULE.md"),                 # 公共规则，不在工作区里
        ("AGENT.md", ctx.folder / "AGENT.md"),              # 这个 Agent 的人设
        ("user/USER.md", ctx.user_folder / "USER.md"),      # 用户的基本信息，所有 Agent 共用
        ("BOOTSTRAP.md", ctx.folder / "BOOTSTRAP.md"),      # 首次引导，完成后会被删掉
        ("user/MEMORY.md", ctx.user_folder / "MEMORY.md"),  # 关于用户的记忆，所有 Agent 共用
        ("MEMORY.md", ctx.folder / "MEMORY.md"),            # 这个 Agent 自己的工作经验
    ]

def onboarding_done(ctx):
    text = (ctx.folder / "AGENT.md").read_text(encoding='utf-8')
    return PLACEHOLDER not in text

def build_system_prompt(ctx):
    ensure_workspace()
    parts = []
    for name, path in prompt_files(ctx):
        if not path.exists():
            continue
        if name == "BOOTSTRAP.md" and onboarding_done(ctx):
            path.unlink()
            print("【系统】初始化已完成，已删除 BOOTSTRAP.md")
            continue
        text = path.read_text(encoding="utf-8")
        parts.append(f'<file name = "{name}">\n{text}\n</file>')
    return "\n\n".join(parts)

# 读取用户取给模型的名字
def get_agent_name(ctx):
    default_name = "无嗣"
    path = ctx.folder / "AGENT.md"

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return default_name

    prefix = "- **名字**:"

    for line in text.splitlines():
        # 去掉首尾空白，同时兼容中文冒号
        line = line.strip().replace("：", ":", 1)

        if line.startswith(prefix):
            # 取出冒号后面的名字
            name = line[len(prefix):].strip()

            # 还没填写名字时，使用默认名字
            if not name or name == PLACEHOLDER:
                return default_name

            return name

    return default_name

if __name__ == "__main__":
    from agents.bots import main_ctx
    print(build_system_prompt(main_ctx()))
