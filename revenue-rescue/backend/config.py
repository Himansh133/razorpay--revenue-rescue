import os
from pathlib import Path
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env", override=True)

DATA_DIR = os.getenv("DATA_DIR", str(BASE_DIR / "data"))
OUTPUT_DIR = os.getenv("OUTPUT_DIR", str(BASE_DIR / "output"))
DB_PATH = os.getenv("DB_PATH", str(Path(OUTPUT_DIR) / "audit_trail.db"))

RAZORPAY_KEY_ID = os.getenv("RAZORPAY_KEY_ID", "rzp_test_mock_id")
RAZORPAY_KEY_SECRET = os.getenv("RAZORPAY_KEY_SECRET", "mock_key_secret")
RAZORPAY_WEBHOOK_SECRET = os.getenv("RAZORPAY_WEBHOOK_SECRET", "test_webhook_secret")

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")

os.makedirs(OUTPUT_DIR, exist_ok=True)
