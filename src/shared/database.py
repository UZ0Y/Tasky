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
            await db.execute("""
            CREATE TABLE IF NOT EXISTS PROACTIVE_QUEUE (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                channel_id INTEGER,
                content TEXT,
                status TEXT DEFAULT 'PENDING',
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

    async def label_missing_author_names(self, author_id: int, author_name: str):
        """Labels existing messages from an author that were saved without a display name."""
        async with aiosqlite.connect(self.db_path) as db:
            await db.execute(
                """
                UPDATE MESSAGE_HISTORY
                SET author_name = ?
                WHERE author_id = ?
                  AND (author_name IS NULL OR author_name = '')
                """,
                (author_name, author_id),
            )
            await db.commit()
    
    async def get_last_channel_id(self):
        """Retrieves the channel_id of the most recent message logged in the database."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT channel_id FROM MESSAGE_HISTORY ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
            
    async def get_channel_history(self, channel_id: int, limit: int = 15):
        """Retrieves recent message history for a given channel for LLM context."""
        async with aiosqlite.connect(self.db_path) as db:
            async with db.execute(
                "SELECT author_name, content, timestamp FROM MESSAGE_HISTORY WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
                (channel_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Return in chronological order
                rows.reverse()
                return rows
