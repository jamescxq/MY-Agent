from config import WORKSPACE

PROTECTED = ["RULE.md"]

def safe_path(path):
    root = WORKSPACE.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return None
    if any(part.lower() == ".git" for part in target.relative_to(root).parts):
        return None
    if target.name.startswith(".env"):
        return None
    return target

if __name__ == "__main__":
    print(safe_path("AGENT.md"))     # 应该显示完整路径
    print(safe_path(".env"))         # 应该是 None
    print(safe_path(".env.local"))   # 应该是 None
    print(safe_path("../a.md"))      # 应该是 None
    print(safe_path(".git/config"))          # 应该是 None
    print(safe_path(".GIT/hooks/pre-commit"))  # 应该是 None