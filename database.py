import aiosqlite

# The database file name
DB_NAME = "Tasks.db"

async def initialize_db():
    """Initializes the database and creates the necessary tables."""
    async with aiosqlite.connect(DB_NAME) as db:
        # Note: 'id' is already PRIMARY KEY, 'head' cannot be a second PRIMARY KEY.
        # Use UNIQUE if you don't want duplicate task titles.
        await db.execute("""
            CREATE TABLE IF NOT EXISTS TASKS (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                author_id INTEGER,
                head TEXT UNIQUE,
                body TEXT,
                timestamp TEXT
            )
        """)
        await db.commit()

async def add_task(author_id, head, body, iso_time_stamp):
    """Inserts a new task into the database."""
    async with aiosqlite.connect(DB_NAME) as db:
        await db.execute(
            "INSERT INTO TASKS (author_id, head, body, timestamp) VALUES (?, ?, ?, ?)",
            (author_id, head, body, iso_time_stamp)
        )
        await db.commit()