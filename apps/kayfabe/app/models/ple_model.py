from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import (
    JSON,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
    func,
)
from sqlmodel import Field, SQLModel

from database import Base


class PleModel(SQLModel, table=True):
    """
    PLE(월별 프리미엄 라이브 이벤트) 메타 정보 테이블.

    ENTITY_RULE.md: 모든 테이블은 int PK `id`를 가진다.
    """

    __tablename__ = "ples"
    metadata = Base.metadata

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"name": "id"},
    )

    slug: str = Field(
        sa_column=Column(String(64), nullable=False, unique=True, index=True)
    )
    month: int = Field(
        sa_column=Column(Integer, nullable=False, index=True)
    )
    label: str = Field(
        sa_column=Column(String(128), nullable=False)
    )
    description: str = Field(
        sa_column=Column(String(512), nullable=False)
    )
    year: int = Field(
        default=2026,
        sa_column=Column(Integer, nullable=False, index=True),
    )
    # PLE 개최 시각(UTC). 이 값이 현재 시각을 지났을 때만 자동 finished 처리.
    event_at: Optional[datetime] = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True, index=True),
    )
    created_at: datetime = Field(
        sa_column=Column(
            DateTime(timezone=True),
            server_default=func.now(),
            nullable=False,
        )
    )


class PleMatchModel(SQLModel, table=True):
    """
    PLE에 속한 개별 경기(매치) 정보.

    - `match_key`: 프론트/백엔드가 공유하는 경기 식별자 (예: "rr-2026-01-main")
    - `result_*`: 실제 결과가 확정되면 기록
    """

    __tablename__ = "ple_matches"
    __table_args__ = (
        UniqueConstraint("ple_id", "match_key", name="uq_ple_matches_ple_id_match_key"),
    )
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

    match_key: str = Field(
        sa_column=Column(String(128), nullable=False, index=True)
    )
    title: str = Field(
        sa_column=Column(String(255), nullable=False)
    )
    card_variant: str = Field(
        default="sideA",
        sa_column=Column(String(16), nullable=False),
    )
    format: str = Field(
        default="singles",
        sa_column=Column(String(16), nullable=False),
    )
    status: str = Field(
        default="upcoming",
        sa_column=Column(String(16), nullable=False, index=True),
    )

    # 경기 구성(선수/팀/배당 등) — 프론트가 보드 렌더링에 사용
    left: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    right: Optional[dict] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    competitors: Optional[list] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )
    bookmaker_decimal: Optional[object] = Field(
        default=None,
        sa_column=Column(JSON, nullable=True),
    )

    # 실제 결과 (확정 전에는 None)
    result_winner: Optional[str] = Field(
        default=None,
        sa_column=Column(String(255), nullable=True),
    )
    result_pick: Optional[str] = Field(
        default=None,
        sa_column=Column(String(32), nullable=True),
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


class PlePredictionModel(SQLModel, table=True):
    """
    사용자(또는 클라이언트)의 예측 기록.

    - `client_id`: 프론트에서 발급한 클라이언트 식별자(로그인 없이도 예측 저장용)
    - `pick`: 선택(예: "left" / "right" / "2" 등)
    - `is_correct`: 결과 확정 시 True/False로 기록 (미확정이면 None)
    """

    __tablename__ = "ple_predictions"
    __table_args__ = (
        UniqueConstraint(
            "ple_match_id",
            "client_id",
            name="uq_ple_predictions_match_client",
        ),
    )
    metadata = Base.metadata

    id: Optional[int] = Field(
        default=None,
        primary_key=True,
        sa_column_kwargs={"name": "id"},
    )

    ple_match_id: int = Field(
        sa_column=Column(
            Integer,
            ForeignKey("ple_matches.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        )
    )
    client_id: str = Field(
        sa_column=Column(String(128), nullable=False, index=True)
    )
    pick: str = Field(
        sa_column=Column(String(32), nullable=False)
    )

    is_correct: Optional[bool] = Field(
        default=None,
        sa_column=Column(Boolean, nullable=True, index=True),
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