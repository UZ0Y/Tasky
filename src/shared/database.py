import aiosqlite
from src.shared.config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def initialize_db(self):
        """Initializes the database and creates the necessary tables."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS TASKS (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER,
                    head TEXT UNIQUE,
                    body TEXT,
                    timestamp TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS MESSAGE_HISTORY (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER,
                    author_name TEXT,
                    channel_id INTEGER,
                    content TEXT,
                    timestamp TEXT
                )
            """)
            await db.commit()

    async def add_task(self, author_id, head, body, iso_time_stamp):
        """Inserts a new task into the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO TASKS (author_id, head, body, timestamp) VALUES (?, ?, ?, ?)",
                (author_id, head, body, iso_time_stamp)
            )
            await db.commit()

    async def add_message_history(self, author_id, author_name, channel_id, content, iso_time_stamp):
        """Inserts a new message log into the database."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                "INSERT INTO MESSAGE_HISTORY (author_id, author_name, channel_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (author_id, author_name, channel_id, content, iso_time_stamp)
            )
            await db.commit()