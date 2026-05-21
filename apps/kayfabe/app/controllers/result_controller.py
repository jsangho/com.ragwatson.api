from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from kayfabe.app.repositories.result_repository import ResultRepository
from kayfabe.app.schemas.result_schema import PleResultsResponse
from kayfabe.app.services.result_service import ResultService


class ResultController:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = ResultRepository(db)
        self.service = ResultService(self.repo)

    async def list_results(self, year: int) -> PleResultsResponse:
        return await self.service.list_results(year)