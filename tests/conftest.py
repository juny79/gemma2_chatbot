"""
pytest fixtures — async DB, FastAPI TestClient
"""
import asyncio
import sys
import os
from pathlib import Path

import pytest
import pytest_asyncio

# inference/ 를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).parent.parent / "inference"))

# 테스트용 DB 경로를 임시 파일로 교체
os.environ.setdefault("DB_PATH", ":memory:")
os.environ.setdefault("GGUF_MODEL_PATH", "dummy_model.gguf")  # 모델 로딩 방지

# ─── async event loop ──────────────────────────────────────────────────────────
@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


# ─── in-memory database ────────────────────────────────────────────────────────
@pytest_asyncio.fixture
async def db():
    """초기화된 인메모리 DB 연결을 제공하는 fixture"""
    import database as db_module
    import aiosqlite

    # config 의존성을 우회하고 in-memory DB 사용
    db_module.DB_PATH = Path(":memory:")
    async with aiosqlite.connect(":memory:") as conn:
        await conn.execute("PRAGMA journal_mode=WAL")
        await conn.execute("PRAGMA foreign_keys = ON")
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                title TEXT NOT NULL,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
            """
        )
        await conn.execute(
            """
            CREATE TABLE IF NOT EXISTS messages (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id TEXT NOT NULL,
                role TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id) ON DELETE CASCADE
            )
            """
        )
        await conn.commit()
        # DB_PATH를 None으로 설정하고 직접 연결 객체를 patch하는 방식 대신
        # fixture 에서는 독립 connect를 사용
        yield conn
