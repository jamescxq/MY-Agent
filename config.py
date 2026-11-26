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
GUESTS_DIR = WORKSPACE / "guests"          # 每位访客一个文件夹，里面是关于他的记忆
STATE_DB = WORKSPACE / "state.db"       # 数据库：Agent 档案、会话、成员名单
DB_BACKUPS = WORKSPACE / "db-backups"      # 数据库的备份，一天一份
TICK_SECONDS = 60                          # 定时提醒：每隔多少秒看一次有没有到点的事。只是查一下数据库，不调模型

# 搜索和读网页走哪条路：
#   auto    自动（默认）：配了搜索服务的密钥就用我们自己写的工具；没配、但模型那边的接口自带搜索，就让服务器去搜
#   own     只用我们自己写的工具
#   server  只让模型那边的服务器去做（那边不带的话，退回用自己的）
WEB_MODE = os.getenv("WEB_MODE", "auto")
SEARCH_PROVIDER = os.getenv("SEARCH_PROVIDER", "")      # 指定用哪家搜索服务（tavily、bocha）。不填就用第一个配了密钥的
SEARCH_KEYS = {                                        # 各家搜索服务的密钥，只从 .env 读
    "tavily": os.getenv("TAVILY_API_KEY", ""),
    "bocha": os.getenv("BOCHA_API_KEY", ""),
}
MODEL = os.getenv("MODEL", "claude-opus-5-5")
# 每天最多用多少 token（发的加上回的）。到了就不再调模型，告诉用户，第二天自动恢复。0 表示不限。见 agents/audit/budget.py
DAILY_TOKEN_LIMIT = int(os.getenv("DAILY_TOKEN_LIMIT", "2000000"))
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