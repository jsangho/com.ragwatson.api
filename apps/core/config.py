import os
from pathlib import Path
from typing import Optional

from dotenv import load_dotenv

_backend_dir = Path(__file__).resolve().parents[2]
load_dotenv(_backend_dir / ".env")
load_dotenv()


def _normalize_postgres_async_url(url: str) -> str:
    """Use psycopg (v3) driver; plain postgresql:// defaults to psycopg2 in SQLAlchemy."""
    if url.startswith("postgresql+psycopg"):
        return url
    if url.startswith("postgresql://"):
        return "postgresql+psycopg://" + url.removeprefix("postgresql://")
    if url.startswith("postgres://"):
        return "postgresql+psycopg://" + url.removeprefix("postgres://")
    return url


_raw_db = os.getenv("DATABASE_URL")
DATABASE_URL: Optional[str] = None
if _raw_db:
    DATABASE_URL = _normalize_postgres_async_url(_raw_db.strip())
