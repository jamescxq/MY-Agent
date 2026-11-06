from agents.tools.guard import safe_path, PROTECTED

EDIT_FILE_TOOL = {
    "name": "edit_file",
    "description": (
        "修改 workspace 里已有文件的一部分：把 old_text 替换成 new_text。"
        "old_text 必须和原文一字不差，并且在文件里只出现一次，不确定原文时先用 read_file 看。"
        "old_text 留空表示在文件末尾追加 new_text。"
        "修改已有文件优先用这个工具，不要整个重写。"
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "path": {
                "type": "string",
                "description": "文件路径，相对于 workspace，例如 MEMORY.md",
            },
            "old_text": {
                "type": "string",
                "description": "要被替换的原文。留空表示追加到文件末尾",
            },
            "new_text": {
                "type": "string",
                "description": "替换后的新内容",
            },
        },
        "required": ["path", "old_text", "new_text"],
    },

}

def edit_file(path, old_text, new_text):
    target = safe_path(path)
    if target is None:
        return f"拒绝：{path} 不在 workspace 里"
    if target.name in PROTECTED:
        return f"拒绝：{path} 受保护，不能修改"
    if not target.is_file():
        return f"找不到文件：{path}，可以先用 list_file 看看目录里有什么"


    text = target.read_text(encoding="utf-8")

    if old_text == "":
        if not text.endswith("\n"):
            text += "\n"
        target.write_text(text + new_text + "\n", encoding="utf-8")
        return f"已在{path}末尾追加"

    count = text.count(old_text)
    if count == 0:
        return f"没找到要替换的文字，请先用 read_file 看看 {path} 的原文"
    if count >1:
        return f"找到 {count} 处，不知道改哪一处。请在 old_text 里多带一点前后文，让它只出现一次"
    target.write_text(text.replace(old_text, new_text), encoding="utf-8")
    return f"已修改{path}"

if __name__ == "__main__":
    from config import WORKSPACE

    test = WORKSPACE / "test_edit.md"
    test.write_text("苹果\n香蕉\n苹果", encoding="utf-8")    # 造一个临时文件，末尾故意不带换行

    print(edit_file("test_edit.md", "香蕉", "橘子"))         # 应该：已修改
    print(edit_file("test_edit.md", "苹果", "梨"))           # 应该：找到 2 处
    print(edit_file("test_edit.md", "西瓜", "梨"))           # 应该：没找到
    print(edit_file("test_edit.md", "", "葡萄"))             # 应该：已追加
    print(edit_file("RULE.md", "这句话不存在", "x"))          # 应该：拒绝，受保护
    print(edit_file("../config.py", "这句话不存在", "x"))     # 应该：拒绝，不在 workspace 里
    print(edit_file("不存在.md", "x", "y"))                   # 应该：找不到文件

    print("----- 临时文件最后的内容 -----")
    print(test.read_text(encoding="utf-8"))
    test.unlink()                                            # 测完删掉临时文件

