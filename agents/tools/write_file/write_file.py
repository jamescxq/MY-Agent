from agents.tools.guard import safe_path, PROTECTED

WRITE_FILE_TOOL = {
    "name": "write_file",
    "description": (
        "把 content 写进 workspace 里的文件。文件不存在就新建，存在就整个覆盖"
        "只改已有文件的一部分时，用 edit_file，不要用这个工具。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径，相对于 workspace，例如 memory/2026-11-04.md",
            },
            "content": {
                "type": "string",
                "description": "文件的完整内容",
            },
        },
        "required": ["path", "content"],
    },
}

def write_file(path, content):
    target = safe_path(path)
    if target is None:
        return f"拒绝：{path} 不在 workspace 里"
    if target.name in PROTECTED:
        return f"拒绝：{path} 受保护，不能修改"
    if target.is_dir():
        return f"拒绝：{path} 是文件夹，不是文件"

    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(content, encoding="utf-8")
    return f"已写入{path}"

if __name__ == "__main__":
    from config import WORKSPACE

    print(write_file("test_write/note.md", "第一版"))    # 应该：已写入（自动建文件夹）
    print(write_file("test_write/note.md", "第二版"))    # 应该：已写入（覆盖旧内容）
    print(write_file("RULE.md", "x"))                    # 应该：拒绝，受保护
    print(write_file("../test_outside.md", "x"))         # 应该：拒绝，不在 workspace 里
    print(write_file("", "x"))                           # 应该：拒绝，是文件夹

    test = WORKSPACE / "test_write" / "note.md"
    print("----- 文件最后的内容 -----")
    print(test.read_text(encoding="utf-8"))              # 应该：第二版
    test.unlink()                                        # 测完删掉临时文件
    test.parent.rmdir()                                  # 再删掉临时文件夹