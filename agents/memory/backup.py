import subprocess
from config import WORKSPACE

# 不进 git 备份的东西。state.db* 包括数据库本身和 db-backups/ 里的备份，
# 它们是二进制文件，git 存不好，另外由 agents/store 里的 backup_db() 备份。
EXCLUDE = ".idea/\nstate.db*\n"

def run_git(*args):
    return subprocess.run(
        ["git", "-c", "core.hooksPath=/dev/null",
         "-c", "user.name=MY-Agent", "-c", "user.email=my-agent@localhost", *args],
        cwd=WORKSPACE, capture_output=True, text=True, encoding="utf-8", errors="replace",
    )

def backup_workspace(message):
    try:
        if not (WORKSPACE / ".git").exists():
            run_git("init")
        # 每次都重写一遍忽略名单：这样以前建好的工作区也能拿到新加的规则
        (WORKSPACE / ".git" / "info" / "exclude").write_text(EXCLUDE, encoding="utf-8")
        run_git("add", "-A")
        if run_git("diff", "--cached", "--quiet").returncode == 0:
            return
        result = run_git("commit", "-m", message)
        if result.returncode != 0:
            print(f"【警告】工作区备份失败：{result.stderr.strip()}")
    except OSError as exc:
        print(f"【警告】工作区备份失败：{exc}")