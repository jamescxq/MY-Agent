from agents.tools.guard import safe_path

def need_approval(name, args):
    if name == "write_file":
        target = safe_path(args.get("path",""))
        return target is not None and target.is_file()
    return False

def ask_user(name, args):
    size = len(args.get("content", ""))
    answer = input(f"[审批]{name}想覆盖{args["path"]},新内容{size}字。同意吗?(y/n)")
    return answer.strip().lower() == "y"

if __name__ == "__main__":
    print(need_approval("write_file", {"path": "MEMORY.md"}))      # 应该：True，要覆盖已有文件
    print(need_approval("write_file", {"path": "不存在.md"}))       # 应该：False，新建文件
    print(need_approval("read_file", {"path": "MEMORY.md"}))       # 应该：False，只读
    print(need_approval("write_file", {"path": "../config.py"}))   # 应该：False，工具自己会拒绝
