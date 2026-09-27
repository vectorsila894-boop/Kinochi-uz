import aiosqlite


class Database:
    def __init__(self, path: str):
        self.path = path

    async def init(self):
        async with aiosqlite.connect(self.path) as db:
            await db.execute("""
                CREATE TABLE IF NOT EXISTS movies (
                    code TEXT PRIMARY KEY,
                    file_id TEXT NOT NULL,
                    title TEXT
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS users (
                    user_id INTEGER PRIMARY KEY
                )
            """)
            await db.execute("""
                CREATE TABLE IF NOT EXISTS requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id INTEGER,
                    code TEXT,
                    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                )
            """)
            await db.commit()

    # --- Movies ---
    async def add_movie(self, code: str, file_id: str, title: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO movies (code, file_id, title) VALUES (?, ?, ?)",
                (code, file_id, title),
            )
            await db.commit()

    async def update_movie(self, code: str, file_id: str, title: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "UPDATE movies SET file_id = ?, title = ? WHERE code = ?",
                (file_id, title, code),
            )
            await db.commit()

    async def get_movie(self, code: str):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute(
                "SELECT file_id, title FROM movies WHERE code = ?", (code,)
            )
            row = await cursor.fetchone()
            return row if row else None

    async def delete_movie(self, code: str) -> bool:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("DELETE FROM movies WHERE code = ?", (code,))
            await db.commit()
            return cursor.rowcount > 0

    async def list_movies(self):
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT code, title FROM movies ORDER BY CAST(code AS INTEGER)")
            return await cursor.fetchall()

    async def count_movies(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM movies")
            row = await cursor.fetchone()
            return row[0]

    # --- Users ---
    async def add_user(self, user_id: int):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT OR IGNORE INTO users (user_id) VALUES (?)", (user_id,)
            )
            await db.commit()

    async def count_users(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM users")
            row = await cursor.fetchone()
            return row[0]

    # --- Requests (statistika uchun) ---
    async def log_request(self, user_id: int, code: str):
        async with aiosqlite.connect(self.path) as db:
            await db.execute(
                "INSERT INTO requests (user_id, code) VALUES (?, ?)", (user_id, code)
            )
            await db.commit()

    async def count_requests(self) -> int:
        async with aiosqlite.connect(self.path) as db:
            cursor = await db.execute("SELECT COUNT(*) FROM requests")
            row = await cursor.fetchone()
            return row[0]
