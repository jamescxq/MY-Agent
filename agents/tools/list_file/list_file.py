from agents.tools.guard import safe_path

LIST_FILE_TOOL = {
    "name": "list_file",
    "description": "列出工作空间（workspace）里某个文件夹下的文件和子文件夹。不知道有哪些文件时先调用它，再用 read_file 读具体文件。文件夹名后面带 /。",
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件夹路径，相对于 workspace，例如 memory。不填就是 workspace 根目录",
            },
        },
    },
}

def list_file(path=""):
    target = safe_path(path)
    if target is None:
        return f"拒绝：{path} 不在 workspace 里"
    if not target.is_dir():
        return f"找不到文件夹：{path}"

    names = []
    for item in sorted(target.iterdir()):
        if item.is_dir():
            names.append(item.name + "/")
        else:
            names.append(item.name)

    if not names:
        return "空文件夹"
    return "\n".join(names)

if __name__ == "__main__":
    print(list_file())               # 应该列出 AGENT.md、MEMORY.md 等
    print(list_file("../agents"))    # 应该被拒绝
    print(list_file("不存在"))        # 应该提示找不到