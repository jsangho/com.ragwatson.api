from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


class ClientPleCompetitor(BaseModel):
    name: str
    isChampion: bool | None = None


class ClientPleMatchCard(BaseModel):
    """프론트가 보내는 매치 카드(최소 필드만)"""

    id: str = Field(..., description="클라이언트 match_key")
    title: str
    cardVariant: Literal["sideA", "sideB"] = "sideA"
    format: Literal["singles", "multi"] = "singles"
    left: ClientPleCompetitor | None = None
    right: ClientPleCompetitor | None = None
    competitors: list[ClientPleCompetitor] | None = None
    bookmakerDecimal: Any | None = None


class SyncFromClientRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    slug: str
    label: str
    month: int
    year: int = 2026
    matches: list[ClientPleMatchCard]


class PleMatchResult(BaseModel):
    winnerSide: Literal["left", "right"] | None = None
    winnerIndex: int | None = None
    winnerName: str | None = None


class PleBoardMatch(BaseModel):
    id: str
    dbId: int
    title: str
    cardVariant: Literal["sideA", "sideB"]
    format: Literal["singles", "multi"]
    left: dict | None = None
    right: dict | None = None
    competitors: list[dict] | None = None
    bookmakerDecimal: Any | None = None
    status: str
    result: PleMatchResult | None = None
    siteVotes: dict
    locked: bool
    myPick: str | None = None


class PleBoard(BaseModel):
    slug: str
    label: str
    month: int
    year: int
    status: Literal["upcoming", "live", "finished"]
    finishedAt: str | None = None
    matches: list[PleBoardMatch]
    updatedAt: str


class PredictRequest(BaseModel):
    pick: str
    clientId: str


class SetResultRequest(BaseModel):
    """
    실제 결과를 확정하고 예측의 정답/오답을 계산하기 위한 요청.

    - singles: winnerSide=("left"|"right") 사용
    - multi: winnerIndex(0-based) 사용
    - winnerName은 표시용(선택)
    """

    winnerSide: Literal["left", "right"] | None = None
    winnerIndex: int | None = None
    winnerName: str | None = None