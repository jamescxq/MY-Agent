from agents.tools.guard import safe_path

def need_approval(name, args):
    if name not in ("write_file", "edit_file"):
        return False
    if name == "edit_file" and args.get("old_text", "") == "":
        return False
    target = safe_path(args.get("path",""))
    return target is not None and target.is_file()

def ask_user(name, args):
    if name == "write_file":
        detail = f"覆盖整个文件，新内容{len(args.get('content', ''))}字"
    else:
        detail = f"把“{args.get('old_text', '')}”改成“{args.get('new_text', '')}”"
    answer = input(f"[审批]{name}想修改{args['path']}：{detail}。同意吗?(y/n)")
    return answer.strip().lower() == "y"

if __name__ == "__main__":
    print(need_approval("write_file", {"path": "MEMORY.md"}))      # 应该：True，要覆盖已有文件
    print(need_approval("write_file", {"path": "不存在.md"}))       # 应该：False，新建文件
    print(need_approval("read_file", {"path": "MEMORY.md"}))       # 应该：False，只读
    print(need_approval("write_file", {"path": "../config.py"}))   # 应该：False，工具自己会拒绝
    print(need_approval("edit_file", {"path": "MEMORY.md", "old_text": "旧", "new_text": "新"}))  # 应该：True，替换
    print(need_approval("edit_file", {"path": "MEMORY.md", "old_text": "", "new_text": "新"}))    # 应该：False，追加
