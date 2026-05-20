from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from kayfabe.app.repositories.ple_repository import PleRepository
from kayfabe.app.schemas.ple_schema import PleBoard, SetResultRequest, SyncFromClientRequest
from kayfabe.app.services.ple_service import PleService

logger = LAYER_LOG


class PleController:
    def __init__(self, db: AsyncSession) -> None:
        self.repo = PleRepository(db)
        self.service = PleService(self.repo)

    async def get_board(self, slug: str, client_id: str | None) -> PleBoard:
        return await self.service.get_board(slug, client_id=client_id)

    async def sync_from_client(self, req: SyncFromClientRequest) -> PleBoard:
        return await self.service.sync_from_client(req)

    async def predict(self, slug: str, match_key: str, client_id: str, pick: str) -> PleBoard:
        return await self.service.predict(slug, match_key, client_id, pick)

    async def set_result(self, slug: str, match_key: str, req: SetResultRequest) -> PleBoard:
        return await self.service.set_result(slug, match_key, req)

    async def live_stream(self, slug: str, client_id: str | None):
        async for chunk in self.service.live_stream(slug, client_id):
            yield chunk