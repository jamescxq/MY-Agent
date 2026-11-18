import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
LOGS = ROOT.parent / "MY-Agent-logs"
TEMPLATES = ROOT / "templates"
WORKSPACE = ROOT.parent / "MY-Agent-workspace"
USER_DIR = WORKSPACE / "user"              # 用户层：关于用户的事，所有 Agent 共用
BOTS_DIR = WORKSPACE / "bots"              # 每个 Agent 一个文件夹，名字是它的编号
STATE_DB = WORKSPACE / "state.db"         # 数据库：Agent 档案、会话、成员名单
DB_BACKUPS = WORKSPACE / "db-backups"      # 数据库的备份，一天一份
MODEL = os.getenv("MODEL", "claude-opus-5-5")
FEISHU_WEBHOOK = os.getenv("FEISHU_WEBHOOK")
FEISHU_APP_ID = os.getenv("FEISHU_APP_ID")
FEISHU_APP_SECRET = os.getenv("FEISHU_APP_SECRET")
FEISHU_OWNER_ID = os.getenv("FEISHU_OWNER_ID")


def feishu_app(bot_id):
    """某个 Agent 自己的飞书应用机器人，返回 (应用编号, 密钥)。没有配置返回 None。

    在 .env 里这样写（Agent 的编号变大写，横线换成下划线），比如 bot-1：
        FEISHU_APP_ID_BOT_1=...
        FEISHU_APP_SECRET_BOT_1=...
    主 bot 用的是上面的 FEISHU_APP_ID、FEISHU_APP_SECRET，不走这里。
    """
    key = bot_id.upper().replace("-", "_")
    app_id = os.getenv(f"FEISHU_APP_ID_{key}")
    secret = os.getenv(f"FEISHU_APP_SECRET_{key}")
    if app_id and secret:
        return app_id, secret
    return None