from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import Column, DateTime, ForeignKey, Integer, String, UniqueConstraint, func
from sqlmodel import Field, SQLModel

from database import Base


class PleResultModel(SQLModel, table=True):
    """
    PLE 단위 결과(상태/종료 시각).

    - ENTITY_RULE.md: 모든 테이블은 int PK `id`를 가진다.
    - ple_id 는 ples.id 를 참조하며 1:1 관계(UNIQUE)
    """

    __tablename__ = "ple_results"
    __table_args__ = (UniqueConstraint("ple_id", name="uq_ple_results_ple_id"),)
    metadata = Base.metadata

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"name": "id"},
    )

    ple_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("ples.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )

    status: str = Field(
        default="upcoming",
        sa_column=Column(String(16), nullable=False, index=True),
    )

    finished_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True),
    )

    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )
    )
    updated_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            onupdate=func.now(),
            nullable=False,
        )
    )

