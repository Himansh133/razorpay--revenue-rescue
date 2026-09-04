import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))
DB_PATH = os.getenv("DB_PATH", str(Path(OUTPUT_DIR) / "audit_trail.db"))
def normalize_database_url(url: str) -> str:
    """
    Normalizes PostgreSQL DATABASE_URL strings to explicitly use the psycopg v3 dialect (`postgresql+psycopg://`).
    Leaves SQLite and other non-PostgreSQL URLs untouched.
    """
    if not url:
        return url
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url[len("postgres://"):]
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url[len("postgresql://"):]
    return url

RAW_DATABASE_URL = os.getenv("DATABASE_URL", f"sqlite:///{DB_PATH}")
DATABASE_URL = normalize_database_url(RAW_DATABASE_URL)

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock_id")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "mock_key_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

os.makedirs(OUTPUT_DIR, exist_ok=True)
