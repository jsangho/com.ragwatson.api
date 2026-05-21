from __future__ import annotations

from datetime import datetime, timezone

from database import LAYER_LOG
from kayfabe.app.repositories.result_repository import ResultRepository
from kayfabe.app.schemas.result_schema import PleResultsResponse, PleResultRow

logger = LAYER_LOG


def _status_from_event(event_at: datetime | None) -> str:
    if event_at is None:
        return "upcoming"
    return "finished" if datetime.now(timezone.utc) >= event_at else "upcoming"


class ResultService:
    def __init__(self, repo: ResultRepository) -> None:
        self.repo = repo

    async def list_results(self, year: int) -> PleResultsResponse:
        pairs = await self.repo.list_results(year)
        rows: list[PleResultRow] = []
        for ple, result in pairs:
            status = result.status if result else _status_from_event(ple.event_at)
            finished_at = result.finished_at if result else (ple.event_at if status == "finished" else None)
            rows.append(
                PleResultRow(
                    slug=ple.slug,
                    label=ple.label,
                    month=ple.month,
                    year=ple.year,
                    eventAt=ple.event_at,
                    status=status,  # type: ignore[arg-type]
                    finishedAt=finished_at,
                )
            )
        return PleResultsResponse(year=year, results=rows)