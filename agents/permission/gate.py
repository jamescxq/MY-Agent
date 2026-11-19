from agents.permission.guard import safe_path

# 访客在说话的时候，只有这几个工具能用。现有的工具都在里面（用户 2026-11-18 决定放开改文件和发通知）。
# 用"允许名单"而不是"禁止名单"：以后新加的工具（浏览器、邮件）默认访客用不了，要给访客用就加到这里。
GUEST_TOOLS = ("get_time", "read_file", "list_file", "write_file", "edit_file", "notify")

def guest_blocked(ctx, name):
    """现在是访客在说话，而且这个工具不在允许名单里，就返回 True。"""
    return bool(ctx.guest) and name not in GUEST_TOOLS

def need_approval(ctx, name, args):
    """这次工具调用要不要先问用户。（用户 2026-11-18 定的：改文件不用问）

    - 用户自己说话时：现有的工具都不用问。改、删、覆盖文件都直接做（工作区每次对话后有 git 备份，能找回）。
    - 访客说话时：新建、往末尾追加不用问；改或删已有的内容、把已有的文件整个覆盖掉，要问用户。
    以后加了删文件、提交网申、发邮件这类工具，在这里加上"要问"。
    """
    if name not in ("write_file", "edit_file"):
        return False
    if not ctx.guest:
        return False
    if name == "edit_file" and args.get("old_text", "") == "":
        return False
    target = safe_path(ctx, args.get("path",""), write=True)
    return target is not None and target.is_file()

def describe(name, args):
    """把一次要审批的操作说成一句人话，问用户的时候用。命令行和飞书都用这一句。"""
    def short(text):                        # 太长的只显示开头，免得一句话问不完
        return text if len(text) <= 80 else text[:80] + "…"

    path = args.get("path", "")
    if name == "write_file":
        return f"把 {path} 整个覆盖掉，新内容 {len(args.get('content', ''))} 字"
    if args.get("new_text", "") == "":
        return f"把 {path} 里的“{short(args.get('old_text', ''))}”删掉"
    return f"把 {path} 里的“{short(args.get('old_text', ''))}”改成“{short(args.get('new_text', ''))}”"

def ask_user(name, args):
    answer = input(f"[审批]想{describe(name, args)}。同意吗?(y/n)")
    return answer.strip().lower() == "y"

if __name__ == "__main__":
    from agents.bots import main_ctx

    ctx = main_ctx()
    print(need_approval(ctx, "write_file", {"path": "MEMORY.md"}))      # 应该：False，用户说话时覆盖已有文件也不用问
    print(need_approval(ctx, "write_file", {"path": "不存在.md"}))       # 应该：False，新建文件
    print(need_approval(ctx, "read_file", {"path": "MEMORY.md"}))       # 应该：False，只读
    print(need_approval(ctx, "write_file", {"path": "../config.py"}))   # 应该：False，工具自己会拒绝
    print(need_approval(ctx, "edit_file", {"path": "MEMORY.md", "old_text": "旧", "new_text": "新"}))  # 应该：False，用户说话时改一句不用问
    print(need_approval(ctx, "edit_file", {"path": "MEMORY.md", "old_text": "旧", "new_text": ""}))    # 应该：False，用户说话时删一句不用问
    print(need_approval(ctx, "edit_file", {"path": "MEMORY.md", "old_text": "", "new_text": "新"}))    # 应该：False，追加

    from dataclasses import replace
    visiting = replace(ctx, guest="guest-1")        # 访客在说话
    print(need_approval(visiting, "edit_file", {"path": "MEMORY.md", "old_text": "旧", "new_text": "新"}))  # 应该：True，访客说话时改已有内容要问
    print(need_approval(visiting, "write_file", {"path": "MEMORY.md"}))                                    # 应该：True，访客说话时覆盖已有文件要问
    print(need_approval(visiting, "write_file", {"path": "不存在.md"}))                                     # 应该：False，新建文件
    print(need_approval(visiting, "edit_file", {"path": "MEMORY.md", "old_text": "", "new_text": "新"}))    # 应该：False，追加
    print(describe("edit_file", {"path": "MEMORY.md", "old_text": "旧", "new_text": ""}))                  # 应该：把 MEMORY.md 里的“旧”删掉
