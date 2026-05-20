import asyncio
import logging
import os
import selectors
import sys
from collections.abc import AsyncGenerator
from urllib.parse import parse_qsl, urlencode, urlparse, urlunparse

# Windows + psycopg 비동기는 ProactorEventLoop에서 멈출 수 있어 가장 먼저 설정합니다.
if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from dotenv import load_dotenv
from fastapi import HTTPException
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

load_dotenv()

# uvicorn 터미널과 동일 스트림에 출력 (별도 stderr 로거는 reload 시 안 보일 수 있음)
APP_LOG = logging.getLogger("uvicorn.error")
LAYER_LOG = APP_LOG
NEON_DB_LOG = APP_LOG


def configure_db_logging() -> None:
    """Neon DB·레이어 로그가 uvicorn 터미널에 보이도록 레벨만 맞춥니다."""
    APP_LOG.setLevel(logging.INFO)

    for name in (
        "sqlalchemy.engine",
        "sqlalchemy.engine.Engine",
        "sqlalchemy.pool",
        "sqlalchemy.dialects",
        "sqlalchemy.orm",
        "neon.db",
        "secom.layer",
    ):
        logging.getLogger(name).setLevel(logging.WARNING)


def attach_neon_sql_logging(async_engine) -> None:
    """SQLAlchemy echo 대신 이벤트로 Neon SQL 로그를 남깁니다 (reload 후에도 동작)."""
    sync_engine = async_engine.sync_engine
    if getattr(sync_engine, "_neon_sql_logging", False):
        return
    sync_engine._neon_sql_logging = True

    @event.listens_for(sync_engine, "begin")
    def _on_begin(conn) -> None:
        NEON_DB_LOG.info("\n[Neon] -------- transaction start --------")

    @event.listens_for(sync_engine, "commit")
    def _on_commit(conn) -> None:
        NEON_DB_LOG.info("[Neon] -------- COMMIT ok ----------------\n")

    @event.listens_for(sync_engine, "rollback")
    def _on_rollback(conn) -> None:
        NEON_DB_LOG.info("[Neon] -------- ROLLBACK -----------------")

    @event.listens_for(sync_engine, "before_cursor_execute")
    def _on_before(
        conn, cursor, statement, parameters, context, executemany
    ) -> None:
        sql = " ".join(str(statement).split())
        NEON_DB_LOG.info("[Neon]   SQL  %s", sql)
        if parameters:
            NEON_DB_LOG.info("[Neon]   params %s", parameters)


def _async_driver() -> str:
    """Windows에서는 asyncpg, 그 외에는 psycopg 비동기를 사용합니다."""
    return "postgresql+asyncpg" if sys.platform == "win32" else "postgresql+psycopg"


def _strip_asyncpg_query_params(url: str) -> str:
    """asyncpg가 받지 못하는 쿼리 파라미터(sslmode 등)를 제거합니다."""
    parsed = urlparse(url)
    if not parsed.query:
        return url
    kept = [
        (key, value)
        for key, value in parse_qsl(parsed.query, keep_blank_values=True)
        if key.lower() not in {"sslmode", "channel_binding"}
    ]
    return urlunparse(parsed._replace(query=urlencode(kept)))


def _normalize_database_url(url: str | None) -> str | None:
    """Neon 등에서 postgresql:// 로 오는 URL을 비동기 드라이버용으로 맞춥니다."""
    if not url:
        return None
    driver = _async_driver()
    if url.startswith("postgresql+psycopg://"):
        url = "postgresql://" + url.removeprefix("postgresql+psycopg://")
    elif url.startswith("postgresql+asyncpg://"):
        return _strip_asyncpg_query_params(url)
    if url.startswith("postgresql://"):
        url = url.replace("postgresql://", f"{driver}://", 1)
    elif url.startswith("postgres://"):
        url = url.replace("postgres://", f"{driver}://", 1)
    if driver == "postgresql+asyncpg":
        url = _strip_asyncpg_query_params(url)
    return url


def _engine_connect_args() -> dict:
    """Neon SSL·연결 타임아웃."""
    args: dict = {"timeout": 15}
    if _async_driver() == "postgresql+asyncpg":
        args["ssl"] = "require"
    return args


# Neon PostgreSQL: postgresql+psycopg://user:pass@host/dbname?sslmode=require
DATABASE_URL = _normalize_database_url(os.getenv("DATABASE_URL"))

configure_db_logging()

# 비동기 전용 DB 엔진 (Neon SQL 로그는 attach_neon_sql_logging 이벤트로 출력)
engine = (
    create_async_engine(
        DATABASE_URL,
        echo=False,
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=10,
        connect_args=_engine_connect_args(),
    )
    if DATABASE_URL
    else None
)

if engine is not None:
    attach_neon_sql_logging(engine)

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


async def warmup_db_pool() -> None:
    """첫 API 요청 전 Neon 연결 풀을 예열합니다."""
    if engine is None:
        return
    async with engine.connect() as conn:
        await conn.execute(text("SELECT 1"))


async def init_db() -> None:
    """등록된 ORM 모델 기준으로 테이블을 생성합니다."""
    if engine is None:
        return

    import secom.app.models.user_model  # noqa: F401

    await warmup_db_pool()

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
    """FastAPI Depends용 비동기 DB 세션 (쓰기만 commit, 읽기는 rollback)."""
    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 .env 등에 설정되지 않았습니다.",
        )
    async with AsyncSessionLocal() as session:
        try:
            yield session
            if session.new or session.dirty or session.deleted:
                await session.commit()
            elif session.in_transaction():
                await session.rollback()
        except Exception:
            if session.in_transaction():
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
