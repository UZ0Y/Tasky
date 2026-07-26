from pathlib import Path
import os
import sys
from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parents[2]
load_dotenv(dotenv_path=BASE_DIR / ".env")

TOKEN = os.getenv("TOKEN")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not TOKEN or not GEMINI_API_KEY:
    print("FATAL ERROR: Missing TOKEN or GEMINI_API_KEY in environment variables.")
    sys.exit(1)

DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

DB_PATH = DATA_DIR / "Tasks.db"
LOG_PATH = LOG_DIR / "discord.log"