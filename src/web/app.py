from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
import sys

# إعداد مسار الجذر لضمان عمل الـ imports بشكل صحيح
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import aiosqlite
from src.shared.config import DB_PATH

app = FastAPI(title="Tasky Dashboard")

# دالة مساعدة للاتصال بالداتابيس وإرجاع النتائج كـ Dictionaries
async def fetch_all(query: str, params: tuple = ()):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(query, params) as cursor:
            rows = await cursor.fetchall()
            return [dict(row) for row in rows]

# ================= API ENDPOINTS =================

@app.get("/api/tasks")
async def get_tasks():
    """كل المهمات المخزنة"""
    try:
        tasks = await fetch_all("SELECT * FROM TASKS ORDER BY id DESC")
        return {"status": "success", "data": tasks}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/messages")
async def get_messages():
    """ كل الرسايل المسجلة من الديسكورد"""
    try:
        messages = await fetch_all("SELECT * FROM MESSAGES ORDER BY date DESC LIMIT 100")
        return {"status": "success", "data": messages}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.delete("/api/tasks/{task_id}")
async def delete_task(task_id: int):
    """حذف مهمة معينة"""
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("DELETE FROM TASKS WHERE id = ?", (task_id,))
        await db.commit()
    return {"status": "success", "message": f"Task {task_id} deleted"}

# ================= PAGE ROUTE =================

@app.get("/", response_class=HTMLResponse)
async def read_index():
    """عرض صفحة الـ Dashboard الرئيسية"""
    html_file = Path(__file__).parent / "index.html"
    if not html_file.exists():
        return HTMLResponse(content="<h1>index.html not found</h1>", status_code=404)
    return HTMLResponse(content=html_file.read_text(encoding="utf-8"))