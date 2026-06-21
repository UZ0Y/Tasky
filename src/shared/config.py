from pathlib import Path

# __file__ references the current file (config.py). 
# .resolve() gets the absolute path on the host machine.
# .parents[2] navigates up from shared/ -> src/ -> accountability_project/ root.
BASE_DIR = Path(__file__).resolve().parents[2]

# Define absolute paths to state directories
DATA_DIR = BASE_DIR / "data"
LOG_DIR = BASE_DIR / "logs"

# Ensure directories exist upon initialization
DATA_DIR.mkdir(exist_ok=True)
LOG_DIR.mkdir(exist_ok=True)

# Define target file paths
DB_PATH = DATA_DIR / "Tasks.db"
LOG_PATH = LOG_DIR / "discord.log"