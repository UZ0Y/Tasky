import aiosqlite
<<<<<<< Updated upstream
from datetime import datetime, timezone
from src.shared.config import DB_PATH

class Database:
    def __init__(self, db_path=DB_PATH):
        self.db_path = db_path

    async def initialize_db(self):
        """Creates tables and applies safe, repeatable TASKS schema migrations."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute("PRAGMA journal_mode=WAL;")
            await db.execute("PRAGMA synchronous=NORMAL;")
            await db.execute("PRAGMA busy_timeout=5000;")
            
            await db.execute("""
                CREATE TABLE IF NOT EXISTS TASKS (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    author_id INTEGER,
                    head TEXT,
                    body TEXT,
                    timestamp TEXT,
                    status TEXT NOT NULL DEFAULT 'OPEN',
                    last_updated TEXT,
                    UNIQUE(author_id, head)
                )
            """)

            async with db.execute("PRAGMA table_info(TASKS)") as cursor:
                task_columns = {row[1] for row in await cursor.fetchall()}

            if "status" not in task_columns:
                await db.execute(
                    "ALTER TABLE TASKS ADD COLUMN status TEXT NOT NULL DEFAULT 'OPEN'"
                )
            if "last_updated" not in task_columns:
                await db.execute("ALTER TABLE TASKS ADD COLUMN last_updated TEXT")

            await db.execute(
                """
                UPDATE TASKS
                SET last_updated = timestamp
                WHERE last_updated IS NULL OR last_updated = ''
                """
            )
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
            await db.execute("""
                CREATE TABLE IF NOT EXISTS PENDING_TASKS (
                    author_id INTEGER,
                    channel_id INTEGER,
                    title TEXT,
                    body TEXT,
                    timestamp TEXT,
                    PRIMARY KEY (author_id, channel_id)
                )
            """)
            await db.commit()

    async def add_task(self, author_id, head, body, iso_time_stamp=None):
        """Inserts a new task into the database."""
        timestamp = iso_time_stamp or datetime.now(timezone.utc).replace(microsecond=0).isoformat()
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT INTO TASKS (author_id, head, body, timestamp, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (author_id, head, body, timestamp, "OPEN", timestamp),
            )
            await db.commit()

    async def add_message_history(self, author_id, author_name, channel_id, content, iso_time_stamp):
        """Inserts a new message log into the database."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute(
                "INSERT INTO MESSAGE_HISTORY (author_id, author_name, channel_id, content, timestamp) VALUES (?, ?, ?, ?, ?)",
                (author_id, author_name, channel_id, content, iso_time_stamp)
            )
            await db.commit()

    async def label_missing_author_names(self, author_id: int, author_name: str):
        """Labels existing messages from an author that were saved without a display name."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
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
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            async with db.execute(
                "SELECT channel_id FROM MESSAGE_HISTORY ORDER BY id DESC LIMIT 1"
            ) as cursor:
                row = await cursor.fetchone()
                return row[0] if row else None
            
    async def get_channel_history(self, channel_id: int, limit: int = 15):
        """Retrieves recent message history for a given channel for LLM context."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            async with db.execute(
                "SELECT author_name, content, timestamp FROM MESSAGE_HISTORY WHERE channel_id = ? ORDER BY id DESC LIMIT ?",
                (channel_id, limit)
            ) as cursor:
                rows = await cursor.fetchall()
                # Return in chronological order
                rows.reverse()
                return rows

    async def set_pending_task(self, author_id: int, channel_id: int, title: str, body: str, timestamp: str):
        """Writes or updates a pending task."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT INTO PENDING_TASKS (author_id, channel_id, title, body, timestamp)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(author_id, channel_id) DO UPDATE SET
                    title = excluded.title,
                    body = excluded.body,
                    timestamp = excluded.timestamp
                """,
                (author_id, channel_id, title, body, timestamp)
            )
            await db.commit()

    async def get_pending_task(self, author_id: int, channel_id: int):
        """Retrieves a pending task if it exists."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            async with db.execute(
                "SELECT title, body, timestamp FROM PENDING_TASKS WHERE author_id = ? AND channel_id = ?",
                (author_id, channel_id)
            ) as cursor:
                row = await cursor.fetchone()
                if row:
                    return {"title": row[0], "body": row[1], "timestamp": row[2]}
                return None

    async def delete_pending_task(self, author_id: int, channel_id: int):
        """Deletes a pending task."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute(
                "DELETE FROM PENDING_TASKS WHERE author_id = ? AND channel_id = ?",
                (author_id, channel_id)
            )
            await db.commit()

    async def confirm_pending_task(self, author_id: int, channel_id: int, title: str, body: str, timestamp: str):
        """Atomically confirms a pending task and removes it from the queue."""
        async with aiosqlite.connect(self.db_path, timeout=5.0) as db:
            await db.execute(
                """
                INSERT INTO TASKS (author_id, head, body, timestamp, status, last_updated)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (author_id, title, body, timestamp, "OPEN", timestamp),
            )
            await db.execute(
                "DELETE FROM PENDING_TASKS WHERE author_id = ? AND channel_id = ?",
                (author_id, channel_id)
            )
            await db.commit()
=======
from .config import DB_PATH 

async def initialize_db():
    """Initializes the database and creates the necessary tables."""
    async with aiosqlite.connect(DB_PATH) as db:
        # جدول المهمات الأصلي
        await db.execute("""
            CREATE TABLE IF NOT EXISTS TASKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER,
                head TEXT UNIQUE,
                body TEXT,
                timestamp TEXT
            )
        """)
        
        # الجدول الجديد للرسائل 
        await db.execute("""
            CREATE TABLE IF NOT EXISTS MESSAGES (
                message_id INTEGER PRIMARY KEY,
                author_id INTEGER,
                channel_id INTEGER,
                content TEXT,
                date TEXT
            )
        """)
        await db.commit()

async def add_task(author_id, head, body, iso_time_stamp):
    """Inserts a new task into the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO TASKS (author_id, head, body, timestamp) VALUES (?, ?, ?, ?)",
            (author_id, head, body, iso_time_stamp)
        )
        await db.commit()

# الفنكشن الجديد
async def add_message(message_id, author_id, channel_id, content, date_str):
    """Inserts a logged discord message into the database."""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "INSERT INTO MESSAGES (message_id, author_id, channel_id, content, date) VALUES (?, ?, ?, ?, ?)",
            (message_id, author_id, channel_id, content, date_str)
        )
        await db.commit()
>>>>>>> Stashed changes
