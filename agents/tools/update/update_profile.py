from config import WORKSPACE

ALLOWED = ["AGENT.md","USER.md","MEMORY.md"]

UPDATE_PROFILE_TOOL = {
    "name": "update_profile",
    "description": (
        "更新工作空间里的档案文件。当用户告诉你新的信息,（你的名字、性格、风格，用户的称呼、背景等）时调用。content 必须是更新后的完整文件内容，会整个覆盖原文件。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "name": {
                "type": "string",
                "enum": ALLOWED,
                "description": "要更新的文件名",
            },

            "content": {
                "type": "string",
                "description": "更新后的完整内容",
            },
        },
        "required": ["name", "content"],
    },

}

def update_profile(name,content):
    if name not in ALLOWED:
        return f"拒绝: 不允许修改 {name}"
    path = WORKSPACE / name
    path.write_text(content,encoding="utf-8")
    return f"已更新{name}"

if __name__ == "__main__":
    print(update_profile("RULE.md", "测试"))
    print(update_profile("MEMORY.md", "# MEMORY.md - 长期记忆\n\n测试写入"))

