import subprocess
from config import WORKSPACE

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
            (WORKSPACE / ".git" / "info" / "exclude").write_text(".idea/\n", encoding="utf-8")
        run_git("add", "-A")
        if run_git("diff", "--cached", "--quiet").returncode == 0:
            return
        result = run_git("commit", "-m", message)
        if result.returncode != 0:
            print(f"【警告】工作区备份失败：{result.stderr.strip()}")
    except OSError as exc:
        print(f"【警告】工作区备份失败：{exc}")