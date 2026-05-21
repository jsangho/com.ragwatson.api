from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from kayfabe.app.schemas.ple_schema import (
    MatchResultUpdateSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    PredictionRequestSchema,
)
from kayfabe.app.services.ple_service import PleService

logger = LAYER_LOG


class PleController:
    def __init__(self, db: AsyncSession) -> None:
        self.ple_service = PleService(db)

    async def list_events(self) -> list[PleEventSummarySchema]:
        logger.info("[PleController] list_events -> Service")
        return await self.ple_service.list_events()

    async def get_board(self, slug: str, client_id: str | None = None) -> PleBoardSchema:
        logger.info("[PleController] get_board -> Service — slug=%s", slug)
        return await self.ple_service.get_board(slug, client_id=client_id)

    async def sync_event(self, payload: PleEventSyncSchema) -> PleBoardSchema:
        logger.info(
            "[PleController] sync_event -> Service — slug=%s matches=%d",
            payload.slug,
            len(payload.matches),
        )
        return await self.ple_service.sync_event(payload)

    async def sync_from_cards(
        self, slug: str, matches: list[dict], year: int = 2026
    ) -> PleBoardSchema:
        return await self.ple_service.sync_event_from_cards(slug, matches, year=year)

    async def predict(
        self,
        slug: str,
        match_key: str,
        body: PredictionRequestSchema,
        user_id: int | None = None,
    ) -> PleBoardSchema:
        logger.info(
            "[PleController] predict -> Service — slug=%s match=%s",
            slug,
            match_key,
        )
        return await self.ple_service.record_prediction(
            slug, match_key, body, user_id=user_id
        )

    async def set_result(
        self, slug: str, match_key: str, body: MatchResultUpdateSchema
    ) -> PleBoardSchema:
        return await self.ple_service.set_match_result(slug, match_key, body)

    async def finalize(self, slug: str) -> PleBoardSchema:
        return await self.ple_service.finalize_event(slug)
