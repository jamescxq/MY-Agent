from config import WORKSPACE

PROTECTED = ["RULE.md"]

def safe_path(path):
    root = WORKSPACE.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return None
    return target