import json
from collections import defaultdict
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from database import LAYER_LOG
from kayfabe.app.models.ple_model import (
    PleEventModel,
    PleEventStatus,
    PleMatchModel,
    PleMatchStatus,
    PlePredictionModel,
)
from kayfabe.app.schemas.ple_schema import (
    MatchCardSyncSchema,
    MatchResultSchema,
    PleEventSyncSchema,
)

logger = LAYER_LOG


class PleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_event_by_slug(self, slug: str) -> PleEventModel | None:
        result = await self.db.execute(
            select(PleEventModel)
            .where(PleEventModel.slug == slug)
            .options(selectinload(PleEventModel.matches).selectinload(PleMatchModel.predictions))
        )
        return result.scalar_one_or_none()

    async def list_events(self) -> list[PleEventModel]:
        result = await self.db.execute(
            select(PleEventModel)
            .options(selectinload(PleEventModel.matches))
            .order_by(PleEventModel.month)
        )
        return list(result.scalars().all())

    async def upsert_event_from_sync(self, payload: PleEventSyncSchema) -> PleEventModel:
        event = await self.get_event_by_slug(payload.slug)
        if event is None:
            event = PleEventModel(
                slug=payload.slug,
                label=payload.label,
                month=payload.month,
                year=payload.year,
            )
            self.db.add(event)
            await self.db.flush()
            existing: dict[str, PleMatchModel] = {}
        else:
            event.label = payload.label
            event.month = payload.month
            event.year = payload.year
            existing = {m.match_key: m for m in event.matches}

        if payload.status:
            event.status = payload.status
        seen_keys: set[str] = set()

        for order, card in enumerate(payload.matches):
            seen_keys.add(card.id)
            card_json = card.model_dump(by_alias=True, mode="json")
            row = existing.get(card.id)
            if row is None:
                row = PleMatchModel(
                    event_id=event.id,
                    match_key=card.id,
                    title=card.title,
                    format=card.format,
                    card_variant=card.card_variant,
                    sort_order=order,
                    card_json=json.dumps(card_json, ensure_ascii=False),
                )
                self.db.add(row)
            else:
                row.title = card.title
                row.format = card.format
                row.card_variant = card.card_variant
                row.sort_order = order
                row.card_json = json.dumps(card_json, ensure_ascii=False)

            if card.result:
                self._apply_result_to_row(row, card.result)

        for key, row in existing.items():
            if key not in seen_keys:
                await self.db.delete(row)

        await self.db.flush()
        return event

    def _apply_result_to_row(self, row: PleMatchModel, result: MatchResultSchema) -> None:
        if result.winner_side:
            row.winner_pick = result.winner_side
        elif result.winner_index is not None:
            row.winner_pick = str(result.winner_index)
        if result.winner_name:
            row.winner_name = result.winner_name
        if result.winner_side or result.winner_index is not None or result.winner_name:
            row.status = PleMatchStatus.FINISHED
            row.finished_at = datetime.now(timezone.utc)

    async def set_match_result(
        self,
        slug: str,
        match_key: str,
        result: MatchResultSchema,
        status: str | None = None,
    ) -> PleMatchModel | None:
        event = await self.get_event_by_slug(slug)
        if event is None:
            return None
        row = next((m for m in event.matches if m.match_key == match_key), None)
        if row is None:
            return None
        self._apply_result_to_row(row, result)
        if status:
            row.status = status
        await self.db.flush()
        return row

    async def finalize_event(self, slug: str) -> PleEventModel | None:
        event = await self.get_event_by_slug(slug)
        if event is None:
            return None
        now = datetime.now(timezone.utc)
        event.status = PleEventStatus.FINISHED
        event.finished_at = now
        for match in event.matches:
            if match.status != PleMatchStatus.FINISHED and match.winner_pick:
                match.status = PleMatchStatus.FINISHED
                match.finished_at = now
        await self.db.flush()
        return event

    async def add_prediction(
        self,
        match_id: int,
        client_id: str,
        pick: str,
        user_id: int | None = None,
    ) -> PlePredictionModel:
        logger.info(
            "[PleRepository] add_prediction -> Neon — matchId=%s clientId=%s pick=%s",
            match_id,
            client_id,
            pick,
        )
        prediction = PlePredictionModel(
            match_id=match_id,
            client_id=client_id,
            user_id=user_id,
            pick=pick,
        )
        self.db.add(prediction)
        await self.db.flush()
        logger.info(
            "[PleRepository] add_prediction <- Neon — predictionId=%s",
            prediction.id,
        )
        return prediction

    async def get_prediction(
        self, match_id: int, client_id: str
    ) -> PlePredictionModel | None:
        result = await self.db.execute(
            select(PlePredictionModel).where(
                PlePredictionModel.match_id == match_id,
                PlePredictionModel.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    @staticmethod
    def aggregate_votes(
        match: PleMatchModel,
    ) -> tuple[dict[str, int | list[int]], str | None]:
        if match.format == "multi":
            card = json.loads(match.card_json)
            count = len(card.get("competitors") or [])
            totals: list[int] = [0] * count
            for pred in match.predictions:
                try:
                    idx = int(pred.pick)
                    if 0 <= idx < count:
                        totals[idx] += 1
                except ValueError:
                    continue
            return {"left": 0, "right": 0, "multi": totals}, None

        left = sum(1 for p in match.predictions if p.pick == "left")
        right = sum(1 for p in match.predictions if p.pick == "right")
        return {"left": left, "right": right, "multi": []}, None
