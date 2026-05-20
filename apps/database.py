import asyncio
import logging
import os
import selectors
import sys
from datetime import datetime, timezone
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
    import kayfabe.app.models.ple_model  # noqa: F401
    import kayfabe.app.models.result_model  # noqa: F401

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

        # KayFabe PLE 메타 시드 (slug 기준 upsert)
        await conn.execute(
            text(
                "CREATE TABLE IF NOT EXISTS ples ("
                "id SERIAL PRIMARY KEY, "
                "slug VARCHAR(64) NOT NULL UNIQUE, "
                "month INTEGER NOT NULL, "
                "label VARCHAR(128) NOT NULL, "
                "description VARCHAR(512) NOT NULL, "
                "year INTEGER NOT NULL DEFAULT 2026, "
                "event_at TIMESTAMP WITH TIME ZONE NULL, "
                "created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW() NOT NULL"
                ")"
            )
        )
        await conn.execute(
            text("ALTER TABLE ples ADD COLUMN IF NOT EXISTS event_at TIMESTAMP WITH TIME ZONE")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_ples_month ON ples (month)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_ples_year ON ples (year)")
        )

        # 기존 DB에서도 kayfabe 테이블 스키마를 점진적으로 맞춥니다.
        # (create_all은 기존 테이블 컬럼 추가/변경을 하지 않음)
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS ple_id INTEGER")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS match_key VARCHAR(128)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS title VARCHAR(255)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS card_variant VARCHAR(16)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS format VARCHAR(16)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS status VARCHAR(16)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS \"left\" JSON")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS \"right\" JSON")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS competitors JSON")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS bookmaker_decimal JSON")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS result_winner VARCHAR(255)")
        )
        await conn.execute(
            text("ALTER TABLE ple_matches ADD COLUMN IF NOT EXISTS result_pick VARCHAR(32)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_ple_matches_ple_id ON ple_matches (ple_id)")
        )
        await conn.execute(
            text("CREATE INDEX IF NOT EXISTS ix_ple_matches_match_key ON ple_matches (match_key)")
        )

        # 개최일(event_at)은 UTC 기준 datetime으로 저장합니다.
        # 확정되지 않은 일정은 None으로 두어 자동 finished가 발생하지 않게 합니다.
        event_at_by_slug: dict[str, datetime | None] = {
            "royal-rumble": datetime(2026, 1, 31, tzinfo=timezone.utc),
            "elimination-chamber": datetime(2026, 2, 28, tzinfo=timezone.utc),
            "wrestlemania": datetime(2026, 4, 18, tzinfo=timezone.utc),  # 4/18~4/19 → 시작일 기준
            "backlash": datetime(2026, 5, 9, tzinfo=timezone.utc),
            "money-in-the-bank": datetime(2026, 9, 6, tzinfo=timezone.utc),
            "summerslam": datetime(2026, 8, 1, tzinfo=timezone.utc),  # 8/1~8/2 → 시작일 기준
            "survivor-series": datetime(2026, 11, 28, tzinfo=timezone.utc),
            # 아래는 프론트 목록에는 아직 없지만, 일정만 보관할 수 있도록 남겨둠
            "clash-in-italy": datetime(2026, 5, 31, tzinfo=timezone.utc),
            "night-of-champions": datetime(2026, 6, 27, tzinfo=timezone.utc),
            "crown-jewel": None,  # 11-xx 미확정
        }

        ple_seeds = [
            (1, "royal-rumble", "Royal Rumble", "30인 룰렛 매치로 WrestleMania 출전권을 가르는 시즌 오프닝"),
            (2, "elimination-chamber", "Elimination Chamber", "철장 안 6인 엘리미네이션 챔버로 챔피언을 결정"),
            (3, "stand-and-deliver", "Stand & Deliver", "NXT의 플래그십 PLE, 차세대 스타들의 무대"),
            (4, "wrestlemania", "WrestleMania 42", "WWE 최대의 쇼, 한 해의 클라이맥스"),
            (5, "backlash", "Backlash", "WrestleMania 직후 스토리가 이어지는 첫 메이저 PPV"),
            (6, "money-in-the-bank", "Money in the Bank", "서류가방 래더 매치로 언제든 타이틀 도전권 획득"),
            (7, "king-queen-of-the-ring", "King & Queen of the Ring", "싱글 토너먼트로 왕·여왕을 가리는 중세 테마 PLE"),
            (8, "summerslam", "SummerSlam", "여름 최대 PLE, 빅 매치와 라이벌의 절정"),
            (9, "bash-in-berlin", "Bash in Berlin", "독일 베를린에서 열리는 국제 스펙터클 이벤트"),
            (10, "bad-blood", "Bad Blood", "헬 인 어 셀 중심의 격렬한 페우드 클리맥스"),
            (11, "survivor-series", "Survivor Series: WarGames", "서바이버 시리즈: 워게임즈로 시즌을 마무리"),
        ]
        for month, slug, label, description in ple_seeds:
            await conn.execute(
                text(
                    "INSERT INTO ples (slug, month, label, description, year, event_at) "
                    "VALUES (:slug, :month, :label, :description, 2026, :event_at) "
                    "ON CONFLICT (slug) DO UPDATE SET "
                    "month = EXCLUDED.month, "
                    "label = EXCLUDED.label, "
                    "description = EXCLUDED.description, "
                    "year = EXCLUDED.year, "
                    "event_at = EXCLUDED.event_at"
                ),
                {
                    "slug": slug,
                    "month": month,
                    "label": label,
                    "description": description,
                    # slug별 확정된 개최일이 있으면 그 값을 사용
                    "event_at": event_at_by_slug.get(slug) or datetime(2026, month, 1, tzinfo=timezone.utc),
                },
            )

        # PLE 결과(ple_results)는 자동 생성하지 않습니다.
        # 운영자/API가 직접 status/finished_at을 기입하는 것을 원칙으로 합니다.


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
