from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel


class PleResultRow(BaseModel):
    slug: str
    label: str
    month: int
    year: int
    eventAt: datetime | None = None
    status: Literal["upcoming", "live", "finished"] = "upcoming"
    finishedAt: datetime | None = None


class PleResultsResponse(BaseModel):
    year: int
    results: list[PleResultRow]