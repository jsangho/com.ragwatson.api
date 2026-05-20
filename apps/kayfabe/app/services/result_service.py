from __future__ import annotations

from database import LAYER_LOG
from kayfabe.app.repositories.result_repository import ResultRepository
from kayfabe.app.schemas.result_schema import PleResultsResponse, PleResultRow

logger = LAYER_LOG


class ResultService:
    def __init__(self, repo: ResultRepository) -> None:
        self.repo = repo

    async def list_results(self, year: int) -> PleResultsResponse:
        pairs = await self.repo.list_results(year)
        rows: list[PleResultRow] = []
        for ple, result in pairs:
            # 결과는 자동 추론하지 않고(DB 직접 기입), ple_results가 없으면 upcoming으로 둡니다.
            status = result.status if result else "upcoming"
            finished_at = result.finished_at if result else None
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
