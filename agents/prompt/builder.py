from config import TEMPLATES
from agents.bots import ensure_workspace, PLACEHOLDER, read_name

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
    """入口启动时调用：先把工作区准备好，再拼提示词。"""
    ensure_workspace()
    return assemble_prompt(ctx)

def assemble_prompt(ctx):
    """只读这个 Agent 的文件、拼成提示词，不碰工作区的结构。评测用的就是这个。"""
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

# 读取用户取给模型的名字。还没取名时用默认名字
def get_agent_name(ctx):
    return read_name(ctx.folder) or "无嗣"

if __name__ == "__main__":
    from agents.bots import main_ctx
    print(build_system_prompt(main_ctx()))
