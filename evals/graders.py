from agents.permission.guard import safe_path

# 检查函数：一道题跑完以后，用代码判断结果对不对。
# 每个函数收到 result（这次跑出来的东西）和这条检查项自己的参数，
# 返回 (对不对, 一句说明)。
#
# result 里有：
#   ctx     临时 Agent 的工牌，用它能找到临时文件夹里的文件
#   reply   Agent 最后说的话
#   tools   这次调用过哪些工具，按顺序，比如 ["read_file", "edit_file"]


def read_text(result, path):
    """读临时文件夹里的文件。路径写法和工具里一样，比如 user/USER.md。读不到返回 None。"""
    target = safe_path(result["ctx"], path)
    if target is None or not target.is_file():
        return None
    return target.read_text(encoding="utf-8")


def file_has(result, path, text):
    content = read_text(result, path)
    if content is None:
        return False, f"没有 {path} 这个文件"
    if text in content:
        return True, ""
    return False, f"{path} 里没有“{text}”"


def file_has_not(result, path, text):
    content = read_text(result, path)
    if content is not None and text in content:
        return False, f"{path} 里出现了不该有的“{text}”"
    return True, ""


def reply_has(result, text):
    if text in result["reply"]:
        return True, ""
    return False, f"回复里没有“{text}”"


def reply_has_not(result, text):
    if text in result["reply"]:
        return False, f"回复里出现了不该有的“{text}”"
    return True, ""


def tool_called(result, name):
    if name in result["tools"]:
        return True, ""
    return False, f"没有调用 {name}，实际调用的是 {result['tools']}"


def tool_not_called(result, name):
    if name in result["tools"]:
        return False, f"调用了不该调用的 {name}"
    return True, ""


# 题目里写的检查项名字 → 对应的检查函数
GRADERS = {
    "文件里有": file_has,
    "文件里没有": file_has_not,
    "回复里有": reply_has,
    "回复里没有": reply_has_not,
    "调用了工具": tool_called,
    "没调用工具": tool_not_called,
}


def check(result, item):
    """跑一条检查项，比如 ("文件里有", "user/USER.md", "James")。返回 (对不对, 一句说明)。"""
    name, *args = item
    if name not in GRADERS:
        return False, f"题目写错了：没有“{name}”这种检查项，可以用的有 {list(GRADERS)}"
    return GRADERS[name](result, *args)


if __name__ == "__main__":
    import tempfile
    from pathlib import Path
    from agents.bots import Ctx

    with tempfile.TemporaryDirectory() as tmp:
        ctx = Ctx(bot_id="eval", folder=Path(tmp) / "bots" / "eval", user_folder=Path(tmp) / "user")
        ctx.user_folder.mkdir(parents=True)
        (ctx.user_folder / "USER.md").write_text("- **称呼**: James", encoding="utf-8")
        result = {"ctx": ctx, "reply": "好的，以后叫你 James", "tools": ["read_file", "edit_file"]}

        print(check(result, ("文件里有", "user/USER.md", "James")))     # 应该：(True, '')
        print(check(result, ("文件里有", "user/USER.md", "Tom")))       # 应该：False，里面没有 Tom
        print(check(result, ("文件里有", "MEMORY.md", "James")))        # 应该：False，没有这个文件
        print(check(result, ("文件里没有", "user/USER.md", "Tom")))     # 应该：(True, '')
        print(check(result, ("回复里有", "James")))                     # 应该：(True, '')
        print(check(result, ("调用了工具", "edit_file")))               # 应该：(True, '')
        print(check(result, ("没调用工具", "write_file")))              # 应该：(True, '')
        print(check(result, ("调用了工具", "notify")))                  # 应该：False，没调用
        print(check(result, ("文件长度", "user/USER.md", 10)))          # 应该：False，题目写错了
