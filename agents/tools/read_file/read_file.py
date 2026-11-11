from agents.tools.guard import safe_path

MAX_CHARS = 5000

READ_FILE_TOOL = {
    "name": "read_file",
    "description": "读取工作空间（workspace）里的文本文件，返回文件内容。一次最多返回 5000 字；文件更长时，按结果末尾的提示传 offset 接着读。只能读 workspace 里面的文件。",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径，相对于 workspace，例如 MEMORY.md 或 memory/2026-11-02.md",
            },
            "offset": {
                "type": "integer",
                "description": "从第几个字开始读，从 0 开始数。不填就从头读。文件太长被截断时，结果末尾会告诉你下一次填多少。",
            },
        },
        "required": ["path"],
    },
}

def read_file(path, offset=0):
    target = safe_path(path)
    if target is None:
        return f"拒绝：{path} 不在WORKSPACE里"
    if not target.is_file():
        return f"找不到文件：{path}，可以先用 list_file 看看目录里有什么"

    text = target.read_text(encoding="utf-8")
    total = len(text)
    if offset < 0 or offset > total:
        return f"offset={offset} 不对，这个文件一共 {total} 个字，offset 要在 0 到 {total} 之间"

    end = offset + MAX_CHARS
    part = text[offset:end]
    if end < total:
        part += f"\n\n......（这次显示第 {offset}～{end} 字，共 {total} 字。继续读请传 offset={end}）"
    return part

if __name__ == "__main__":
    print(read_file("USER.md"))
    print(read_file("../config.py"))
    print(read_file("不存在.md"))