import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent.parent
DATA_DIR = BASE_DIR / "db"
DATA_DIR.mkdir(exist_ok=True)
DB_FILE = DATA_DIR / "store.json"

ANTHROPIC_API_KEY = os.environ.get("ANTHROPIC_API_KEY", "").strip()
CLAUDE_MODEL = os.environ.get("CLAUDE_MODEL", "claude-opus-4-8")

GOOGLE_ADS_MODE = os.environ.get("GOOGLE_ADS_MODE", "mock").strip().lower()
GOOGLE_ADS_DEVELOPER_TOKEN = os.environ.get("GOOGLE_ADS_DEVELOPER_TOKEN", "")
GOOGLE_ADS_CLIENT_ID = os.environ.get("GOOGLE_ADS_CLIENT_ID", "")
GOOGLE_ADS_CLIENT_SECRET = os.environ.get("GOOGLE_ADS_CLIENT_SECRET", "")
GOOGLE_ADS_REFRESH_TOKEN = os.environ.get("GOOGLE_ADS_REFRESH_TOKEN", "")
GOOGLE_ADS_LOGIN_CUSTOMER_ID = os.environ.get("GOOGLE_ADS_LOGIN_CUSTOMER_ID", "")

AUTO_APPLY_OPTIMIZATIONS = os.environ.get("AUTO_APPLY_OPTIMIZATIONS", "false").strip().lower() == "true"
OPTIMIZATION_INTERVAL_MINUTES = int(os.environ.get("OPTIMIZATION_INTERVAL_MINUTES", "60"))


def has_anthropic_key() -> bool:
    return bool(ANTHROPIC_API_KEY)
