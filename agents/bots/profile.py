import json
from dataclasses import dataclass, field

# 档案：花名册里的一行。数据库里记"有这个 Agent"，它的人设和记忆在它自己的文件夹里。
@dataclass
class Profile:
    id: str                    # 英文编号，也是文件夹名，建好以后不变
    name: str                  # 用户取的名字，可以是中文
    description: str = ""      # 一句话说明它是干什么的
    model: str = ""            # 空着表示用默认模型
    packs: list = field(default_factory=list)    # 启用的能力包


def from_row(row):
    """数据库里的一行（字典）→ 档案。"""
    return Profile(
        id=row["id"],
        name=row["name"],
        description=row["description"],
        model=row["model"],
        packs=json.loads(row["packs"]),      # 数据库里存的是一段 JSON 文字，这里转回列表
    )


# AGENT.md 里名字那一行还没填的时候，写的是这段占位文字
PLACEHOLDER = "*(在首次对话时填写，可以是用户给你起的名字)*"

def read_name(folder):
    """从 Agent 文件夹的 AGENT.md 里读出它的名字。没填或读不到返回 None。"""
    try:
        text = (folder / "AGENT.md").read_text(encoding="utf-8")
    except (OSError, UnicodeError):
        return None

    prefix = "- **名字**:"
    for line in text.splitlines():
        # 去掉首尾空白，同时兼容中文冒号
        line = line.strip().replace("：", ":", 1)
        if line.startswith(prefix):
            name = line[len(prefix):].strip()
            if not name or name == PLACEHOLDER:
                return None
            return name
    return None
