from pathlib import PurePosixPath

PROTECTED = ["RULE.md"]

def safe_path(ctx, path, write=False):
    """把模型给的路径变成真正的路径。不允许的返回 None。

    user/ 开头的路径指向公共的 user/ 文件夹，其它路径都在这个 Agent 自己的文件夹里。
    write=True 表示这次是要改文件：没有权限改 user/ 的 Agent 会被拒绝。
    """
    parts = PurePosixPath(str(path).replace("\\", "/")).parts
    if parts and parts[0].lower() == "user":
        if write and not ctx.can_write_user:
            return None
        root = ctx.user_folder.resolve()
        path = "/".join(parts[1:])
    else:
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
    from agents.bots import Ctx, main_ctx
    ctx = main_ctx()
    print(safe_path(ctx, "AGENT.md"))     # 应该显示完整路径，在 bots/main/ 里
    print(safe_path(ctx, "user/USER.md")) # 应该显示完整路径，在 user/ 里
    print(safe_path(ctx, ".env"))         # 应该是 None
    print(safe_path(ctx, ".env.local"))   # 应该是 None
    print(safe_path(ctx, "../a.md"))      # 应该是 None
    print(safe_path(ctx, ".git/config"))          # 应该是 None
    print(safe_path(ctx, ".GIT/hooks/pre-commit"))  # 应该是 None
    print(safe_path(ctx, "state.db"))               # 应该是 None
    print(safe_path(ctx, "STATE.DB"))               # 应该是 None
    print(safe_path(ctx, "db-backups/state.db.2026-11-17.bak"))  # 应该是 None
    print(safe_path(ctx, "../coder/AGENT.md"))      # 应该是 None，别的 Agent 的文件夹
    print(safe_path(ctx, "../../state.db"))         # 应该是 None，数据库
    print(safe_path(ctx, "user/../bots/main/AGENT.md"))   # 应该是 None，想从 user/ 绕出去

    # 换一张别的 Agent 的工牌：它能读 user/，不能改 user/
    other = Ctx(bot_id="coder", folder=ctx.folder.parent / "coder", user_folder=ctx.user_folder)
    print(safe_path(other, "user/USER.md"))              # 应该显示完整路径，可以读
    print(safe_path(other, "user/USER.md", write=True))  # 应该是 None，不能改
    print(safe_path(other, "../main/AGENT.md"))          # 应该是 None，读不到主 bot 的文件夹
