from config import WORKSPACE
from agents.tools.guard import safe_path

MAX_CHARS = 5000

READ_FILE_TOOL = {
    "name": "read_file",
    "description": "读取工作空间（workspace）里的文本文件，返回文件内容。需要查看某个文件的最新内容时调用。只能读 workspace 里面的文件。",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径，相对于 workspace，例如 MEMORY.md 或 memory/2026-11-02.md",
            }
        },
        "required": ["path"],
    },
}

def read_file(path):
    target = safe_path(path)
    if target is None:
        return f"拒绝：{path} 不在WORKSPACE里"
    if not target.is_file():
        return f"找不到文件：{path}"

    text = target.read_text(encoding="utf-8")
    if len(text) > MAX_CHARS:
        return text[:MAX_CHARS] + f"\n\n......(文件太长，只显示{MAX_CHARS}个字，共{len(text)}个字)"
    return text

if __name__ == "__main__":
    print(read_file("USER.md"))
    print(read_file("../config.py"))
    print(read_file("不存在.md"))