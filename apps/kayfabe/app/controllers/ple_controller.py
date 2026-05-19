from sqlalchemy.ext.asyncio import AsyncSession

from database import APP_LOGGER
from kayfabe.app.ple import Ple
from kayfabe.app.schemas.ple_schema import (
    MatchResultUpdateSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    PredictionRequestSchema,
)

logger = APP_LOGGER


class PleController:
    def __init__(self, db: AsyncSession) -> None:
        self.ple = Ple(db)

    async def sync_event(self, payload: PleEventSyncSchema) -> PleBoardSchema:
        logger.info(
            "[PleController] sync_event slug=%s matches=%d",
            payload.slug,
            len(payload.matches),
        )
        await self.ple.repo.upsert_event_from_sync(payload)
        return await self.ple.get_board(payload.slug)

    async def sync_from_cards(
        self, slug: str, matches: list[dict], year: int = 2026
    ) -> PleBoardSchema:
        return await self.ple.sync_event_from_cards(slug, matches, year=year)

    async def get_board(self, slug: str, client_id: str | None = None) -> PleBoardSchema:
        return await self.ple.get_board(slug, client_id=client_id)

    async def list_events(self) -> list[PleEventSummarySchema]:
        return await self.ple.list_events()

    async def predict(
        self,
        slug: str,
        match_key: str,
        body: PredictionRequestSchema,
        user_id: int | None = None,
    ) -> PleBoardSchema:
        return await self.ple.record_prediction(slug, match_key, body, user_id)

    async def set_result(
        self, slug: str, match_key: str, body: MatchResultUpdateSchema
    ) -> PleBoardSchema:
        return await self.ple.set_match_result(slug, match_key, body)

    async def finalize(self, slug: str) -> PleBoardSchema:
        return await self.ple.finalize_event(slug)
