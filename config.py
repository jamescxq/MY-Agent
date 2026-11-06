import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).parent
LOGS = ROOT.parent / "MY-Agent-logs"
TEMPLATES = ROOT / "templates"
WORKSPACE = ROOT.parent / "MY-Agent-workspace"
MODEL = os.getenv("MODEL", "claude-opus-5-5")