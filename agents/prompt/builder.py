# python自带工具Path 专门用来处理文件路径：拼路径、判断文件存不存在、读文件
import shutil
from config import WORKSPACE,TEMPLATES
from pathlib import Path

FILES = ["RULE.md", "AGENT.md", "USER.md", "BOOTSTRAP.md", "MEMORY.md"]
PROFILE_FILES = ["AGENT.md", "USER.md", "MEMORY.md"]    # 每个人自己一份的档案
PLACEHOLDER = "*(在首次对话时填写，可以是用户给你起的名字)*"

def ensure_workspace():
    is_new = not(WORKSPACE / "AGENT.md").exists()
    WORKSPACE.mkdir(exist_ok=True)
    for name in PROFILE_FILES:
        path = WORKSPACE / name
        if not path.exists():
            shutil.copy(TEMPLATES / name, path)
    if is_new:
        shutil.copy(TEMPLATES / "BOOTSTRAP.md", WORKSPACE/ "BOOTSTRAP.md")

def onboarding_done():
    agents = WORKSPACE / "AGENT.md"
    text = agents.read_text(encoding='utf-8')
    return PLACEHOLDER not in text

def build_system_prompt():
    ensure_workspace()
    parts = []
    for name in FILES:
        path = TEMPLATES / name if name == "RULE.md" else WORKSPACE / name
        if not path.exists():
            continue
        if name == "BOOTSTRAP.md" and onboarding_done():
            path.unlink()
            print("【系统】初始化已完成，已删除 BOOTSTRAP.md")
            continue
        text = path.read_text(encoding="utf-8")
        parts.append(f'<file name = "{name}">\n{text}\n</file>')
    return "\n\n".join(parts)

# 读取用户取给模型的名字
def get_agent_name():
    default_name = "无嗣"
    path = WORKSPACE / "AGENT.md"

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
    print(build_system_prompt())