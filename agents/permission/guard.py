
PROTECTED = ["RULE.md"]

def safe_path(ctx, path):
    root = ctx.folder.resolve()
    target = (root / path).resolve()
    if not target.is_relative_to(root):
        return None
    if any(part.lower() == ".git" for part in target.relative_to(root).parts):
        return None
    if target.name.startswith(".env"):
        return None
    # 数据库和它的备份只许代码读写，工具不能碰。Windows 不分大小写，所以先转小写再比
    if target.name.lower().startswith("state.db"):
        return None
    return target

if __name__ == "__main__":
    from agents.bots import main_ctx
    ctx = main_ctx()
    print(safe_path(ctx, "AGENT.md"))     # 应该显示完整路径
    print(safe_path(ctx, ".env"))         # 应该是 None
    print(safe_path(ctx, ".env.local"))   # 应该是 None
    print(safe_path(ctx, "../a.md"))      # 应该是 None
    print(safe_path(ctx, ".git/config"))          # 应该是 None
    print(safe_path(ctx, ".GIT/hooks/pre-commit"))  # 应该是 None
    print(safe_path(ctx, "state.db"))               # 应该是 None
    print(safe_path(ctx, "STATE.DB"))               # 应该是 None
    print(safe_path(ctx, "db-backups/state.db.2026-11-17.bak"))  # 应该是 None