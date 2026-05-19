from datetime import datetime
from enum import StrEnum

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class PleEventStatus(StrEnum):
    UPCOMING = "upcoming"
    LIVE = "live"
    FINISHED = "finished"


class PleMatchStatus(StrEnum):
    SCHEDULED = "scheduled"
    LIVE = "live"
    FINISHED = "finished"


class PleEventModel(Base):
    __tablename__ = "ple_events"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    slug: Mapped[str] = mapped_column(String(64), unique=True, nullable=False, index=True)
    label: Mapped[str] = mapped_column(String(120), nullable=False)
    month: Mapped[int] = mapped_column(Integer, nullable=False)
    year: Mapped[int] = mapped_column(Integer, nullable=False, default=2026)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PleEventStatus.UPCOMING
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    matches: Mapped[list["PleMatchModel"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="PleMatchModel.sort_order",
    )


class PleMatchModel(Base):
    __tablename__ = "ple_matches"
    __table_args__ = (UniqueConstraint("event_id", "match_key", name="uq_ple_event_match_key"),)

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("ple_events.id", ondelete="CASCADE"), index=True)
    match_key: Mapped[str] = mapped_column(String(80), nullable=False)
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    format: Mapped[str] = mapped_column(String(20), nullable=False)
    card_variant: Mapped[str] = mapped_column(String(10), nullable=False, default="sideA")
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    card_json: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=PleMatchStatus.SCHEDULED
    )
    winner_pick: Mapped[str | None] = mapped_column(String(20), nullable=True)
    winner_name: Mapped[str | None] = mapped_column(String(200), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    event: Mapped["PleEventModel"] = relationship(back_populates="matches")
    predictions: Mapped[list["PlePredictionModel"]] = relationship(
        back_populates="match",
        cascade="all, delete-orphan",
    )


class PlePredictionModel(Base):
    __tablename__ = "ple_predictions"
    __table_args__ = (
        UniqueConstraint("match_id", "client_id", name="uq_ple_prediction_match_client"),
    )

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    match_id: Mapped[int] = mapped_column(
        ForeignKey("ple_matches.id", ondelete="CASCADE"), index=True
    )
    client_id: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    pick: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    match: Mapped["PleMatchModel"] = relationship(back_populates="predictions")
