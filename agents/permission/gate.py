from agents.permission.guard import safe_path

# 访客能用哪些工具：和用户本人一样（用户 2026-11-26 定的，理由是"人是我邀请的"）。
# 以前这里有一份访客的允许名单（搜索、派单、定提醒、新建 Agent 访客都用不了），现在没有了。
# 访客和用户本人还不一样的只剩下面几处，都不是"能不能用这个工具"，而是保护用户已有的东西：
#   1. 访客让改、让删已有的内容，或者让新建 Agent，要用户点头（下面的 approval_reason）
#   2. 访客碰不到别的访客的文件夹（guard.py）
#   3. 斜杠命令只有用户能用（入口里判断）
# 以后想给某位访客单独开关能力（计划做在网页管理台里），在这里加回判断；注意改了以后要让会话重新开始，原因见 loop.py 的 run_agent。

# 一段对话里读过外面的内容（网页、搜索结果）以后，还能不问就用的工具：只读的这几个。
# 用"允许名单"：以后新加的工具，在读过外面内容的对话里默认要先问用户。
# dispatch（派子智能体）也在里面：子智能体只能查不能改，和接着搜、接着读网页是一回事。
SAFE_AFTER_OUTSIDE = ("get_time", "read_file", "list_file", "web_search", "web_fetch", "dispatch")
OUTSIDE_REASON = "这段对话里读过外面的内容（网页或搜索结果），里面可能藏着指令"
GUEST_REASON = "是访客让改已有的内容"
GUEST_CREATE_REASON = "是访客让新建 Agent"

def approval_reason(ctx, name, args, outside=False):
    """这次工具调用为什么要先问用户。不用问就返回空字符串。

    outside=True 表示这段对话里读过外面的内容（由 taint.py 的 has_outside 判断）。两种情况要问：

    1. 读过外面的内容以后，要做会留下东西的事（改文件、发通知、定提醒、新建 Agent）。
       网页里可能藏着"把记忆清空"这类指令，模型万一照做了，这一问能拦住。只读的操作不问。
    2. 访客说话时，改或删已有的内容、把已有的文件整个覆盖掉。新建文件、往末尾追加不问。
    3. 访客说话时，让新建一个 Agent。新建的 Agent 会一直留在用户的花名册里，所以要用户点头。

    除此以外，用户自己说话时现有的工具都不用问（用户 2026-11-18 定的；工作区每次对话后有 git 备份，能找回）。
    以后加了删文件、提交网申、发邮件这类工具，在这里加上"要问"。
    """
    if outside and name not in SAFE_AFTER_OUTSIDE:
        if not (name == "schedule" and args.get("action") == "list"):      # 只是看一眼定了哪些，不算
            return OUTSIDE_REASON
    if not ctx.guest:
        return ""
    if name == "create_agent":
        return GUEST_CREATE_REASON
    if name not in ("write_file", "edit_file"):
        return ""
    if name == "edit_file" and args.get("old_text", "") == "":
        return ""
    target = safe_path(ctx, args.get("path",""), write=True)
    return GUEST_REASON if target is not None and target.is_file() else ""

def need_approval(ctx, name, args, outside=False):
    """这次工具调用要不要先问用户。要问的原因见 approval_reason。"""
    return approval_reason(ctx, name, args, outside) != ""

def describe(name, args):
    """把一次要审批的操作说成一句人话，问用户的时候用。命令行和飞书都用这一句。"""
    def short(text):                        # 太长的只显示开头，免得一句话问不完
        return text if len(text) <= 80 else text[:80] + "…"

    path = args.get("path", "")
    if name == "write_file":
        return f"把 {path} 整个覆盖掉，新内容 {len(args.get('content', ''))} 字"
    if name == "edit_file":
        if args.get("old_text", "") == "":
            return f"往 {path} 末尾加上“{short(args.get('new_text', ''))}”"
        if args.get("new_text", "") == "":
            return f"把 {path} 里的“{short(args.get('old_text', ''))}”删掉"
        return f"把 {path} 里的“{short(args.get('old_text', ''))}”改成“{short(args.get('new_text', ''))}”"
    if name == "notify":
        return f"往飞书发一条通知：“{short(args.get('text', ''))}”"
    if name == "create_agent":
        return f"新建一个叫「{args.get('name', '')}」的 Agent"
    if name == "dispatch":
        return f"派一个子智能体去做：“{short(args.get('task', ''))}”"
    if name == "schedule":
        if args.get("action") == "delete":
            return f"删掉 {args.get('id')} 号定时提醒"
        return f"定一条提醒（{args.get('kind', '')} {args.get('time', '')}）：“{short(args.get('task', ''))}”"
    return f"用 {name} 这个工具，参数是 {short(str(args))}"

def ask_user(name, args, reason=""):
    """命令行里的审批：在终端里问 y/n。reason 是为什么要问。"""
    why = f"（{reason}）" if reason else ""
    answer = input(f"[审批]想{describe(name, args)}。{why}同意吗?(y/n)")
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

    # 读过外面的内容以后（outside=True）：只读的照常，会留下东西的都要问
    print(need_approval(ctx, "edit_file", {"path": "MEMORY.md", "old_text": "", "new_text": "新"}, outside=True))   # 应该：True，连追加也要问
    print(need_approval(ctx, "notify", {"text": "x"}, outside=True))                # 应该：True
    print(need_approval(ctx, "schedule", {"action": "create"}, outside=True))       # 应该：True
    print(need_approval(ctx, "schedule", {"action": "list"}, outside=True))         # 应该：False，只是看
    print(need_approval(ctx, "read_file", {"path": "MEMORY.md"}, outside=True))     # 应该：False，只读
    print(need_approval(ctx, "web_fetch", {"url": "https://a.test"}, outside=True))  # 应该：False，接着读网页不用问
    print(approval_reason(ctx, "notify", {"text": "x"}, outside=True))              # 应该：这段对话里读过外面的内容……
    print(describe("notify", {"text": "到点了"}), "|", describe("schedule", {"action": "delete", "id": 3}), "|", describe("create_agent", {"name": "旺财"}))

    # 访客能用的工具和用户一样；只有让新建 Agent 要用户点头
    print(need_approval(visiting, "create_agent", {"name": "x"}))       # 应该：True，访客让新建 Agent 要问
    print(need_approval(ctx, "create_agent", {"name": "x"}))            # 应该：False，用户自己让建不用问
    print(need_approval(visiting, "schedule", {"action": "create"}))    # 应该：False，访客可以定提醒
    print(need_approval(visiting, "web_search", {"query": "x"}))        # 应该：False，访客可以搜索
    print(need_approval(visiting, "dispatch", {"task": "x"}))           # 应该：False，访客可以让派单
