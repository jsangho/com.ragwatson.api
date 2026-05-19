import asyncio
import logging
import os
import selectors
import sys
from collections.abc import AsyncGenerator

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

# uvicorn 터미널과 같은 스트림에 SQL·레이어 로그 출력
APP_LOGGER = logging.getLogger("uvicorn.error")


def configure_db_logging() -> None:
    """SQLAlchemy SQL 로그와 앱 DB 로그가 터미널에 보이도록 설정합니다."""
    for name in (
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "secom",
    ):
        logging.getLogger(name).setLevel(logging.INFO)


def _normalize_database_url(url: str | None) -> str | None:
    """Neon 등에서 postgresql:// 로 오는 URL을 비동기 드라이버용으로 맞춥니다."""
    if not url:
        return None
    if url.startswith("postgresql://"):
        return url.replace("postgresql://", "postgresql+psycopg://", 1)
    if url.startswith("postgres://"):
        return url.replace("postgres://", "postgresql+psycopg://", 1)
    return url


# Neon PostgreSQL: postgresql+psycopg://user:pass@host/dbname?sslmode=require
DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))

configure_db_logging()

# 비동기 전용 DB 엔진 (echo=True → SELECT/INSERT/COMMIT SQL 로그 출력)
engine = (
    create_async_engine(DATABASE_URL, echo=True, pool_pre_ping=True)
    if DATABASE_URL
    else None
)

# 비동기 세션 생성기 (SQLAlchemy 2.0) — autoflush로 add 직후 DB로 전송
AsyncSessionLocal = (
    async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=True,
    )
    if engine is not None
    else None
)


class Base(DeclarativeBase):
    """SQLAlchemy 2.0 Declarative 베이스. ORM 모델은 이 클래스를 상속합니다."""

    pass


async def init_db() -> None:
    """등록된 ORM 모델 기준으로 테이블을 생성합니다."""
    if engine is None:
        return

    import secom.app.models.user_model  # noqa: F401
    import kayfabe.app.models.ple_model  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        await conn.execute(
            text(
                "ALTER TABLE users ADD COLUMN IF NOT EXISTS created_at "
                "TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL"
            )
        )
        await conn.execute(
            text("ALTER TABLE users ADD COLUMN IF NOT EXISTS login_id VARCHAR(50)")
        )
        await conn.execute(
            text(
                "CREATE UNIQUE INDEX IF NOT EXISTS ix_users_login_id "
                "ON users (login_id) WHERE login_id IS NOT NULL"
            )
        )


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI Depends용 비동기 DB 세션 (성공 시 commit, 실패 시 rollback)."""
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def dispose_engine() -> None:
    """앱 종료 시 연결 풀 정리."""
    global engine, AsyncSessionLocal
    if engine is not None:
        await engine.dispose()
    engine = None
    AsyncSessionLocal = None


async def main() -> None:
    """Neon Postgres 연결 확인: backend/apps 에서 python database.py"""
    if engine is None or AsyncSessionLocal is None:
        raise RuntimeError("DATABASE_URL이 .env 에 설정되지 않았습니다.")

    import secom.app.models.user_model  # noqa: F401

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with AsyncSessionLocal() as session:
        result = await session.execute(text("SELECT NOW()"))
        db_time = result.scalar_one()
        print(f"Neon Postgres 연결 성공: {db_time}")

    await dispose_engine()


def _run_async(coro) -> None:
    """Windows에서는 psycopg 비동기용 SelectorEventLoop가 필요합니다."""
    if sys.platform == "win32":
        loop = asyncio.SelectorEventLoop(selectors.SelectSelector())
        try:
            loop.run_until_complete(coro)
        finally:
            loop.close()
        return
    asyncio.run(coro)


if __name__ == "__main__":
    _run_async(main())
