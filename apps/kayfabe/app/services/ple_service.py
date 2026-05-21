"""
PLE(프리미엄 라이브 이벤트) — 경기 목록·예측·결과 비즈니스 로직.

프론트 `wwe-ple-matches.ts` 카드 → sync 후 Neon에 저장, 예측은 ple_predictions에 기록.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from kayfabe.app.models.ple_model import PleEventStatus, PleMatchStatus
from kayfabe.app.repositories.ple_repository import PleRepository
from kayfabe.app.schemas.ple_schema import (
    CompetitorSchema,
    MatchBoardSchema,
    MatchResultSchema,
    MatchResultUpdateSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    PredictionRequestSchema,
    VoteTotalsSchema,
)

logger = LAYER_LOG

PLE_EVENT_META: dict[str, dict[str, Any]] = {
    "royal-rumble": {"label": "Royal Rumble", "month": 1},
    "elimination-chamber": {"label": "Elimination Chamber", "month": 2},
    "stand-and-deliver": {"label": "Stand & Deliver", "month": 3},
    "wrestlemania": {"label": "WrestleMania", "month": 4},
    "backlash": {"label": "Backlash", "month": 5},
    "money-in-the-bank": {"label": "Money in the Bank", "month": 6},
    "king-queen-of-the-ring": {"label": "King & Queen of the Ring", "month": 7},
    "summerslam": {"label": "SummerSlam", "month": 8},
    "bash-in-berlin": {"label": "Bash in Berlin", "month": 9},
    "bad-blood": {"label": "Bad Blood", "month": 10},
    "survivor-series": {"label": "Survivor Series", "month": 11},
}

FINISHED_2026_RESULTS: dict[str, dict[str, MatchResultSchema]] = {
    "royal-rumble": {
        "rr26-gunther-styles": MatchResultSchema(winner_side="left", winner_name="Gunther"),
        "rr26-undisputed": MatchResultSchema(winner_side="left", winner_name="Drew McIntyre"),
        "rr26-women-rumble": MatchResultSchema(winner_index=1, winner_name="Liv Morgan"),
        "rr26-men-rumble": MatchResultSchema(winner_index=0, winner_name="Roman Reigns"),
    },
    "elimination-chamber": {
        "ec26-women": MatchResultSchema(winner_index=0, winner_name="Rhea Ripley"),
        "ec26-women-ic": MatchResultSchema(winner_side="left", winner_name="AJ Lee"),
        "ec26-whc": MatchResultSchema(winner_side="left", winner_name="CM Punk"),
        "ec26-men": MatchResultSchema(winner_index=0, winner_name="Randy Orton"),
    },
    "stand-and-deliver": {
        "sad26-preshow": MatchResultSchema(winner_side="left"),
        "sad26-sol-zaria": MatchResultSchema(winner_side="left", winner_name="Sol Ruca"),
        "sad26-women-na": MatchResultSchema(winner_side="left", winner_name="Tatum Paxley"),
        "sad26-na": MatchResultSchema(winner_side="left", winner_name="Myles Borne"),
        "sad26-tag": MatchResultSchema(winner_side="left", winner_name="The Vanity Project"),
        "sad26-women": MatchResultSchema(winner_index=0, winner_name="Lola Vice"),
        "sad26-nxt": MatchResultSchema(winner_index=0, winner_name="Tony D'Angelo"),
    },
    "wrestlemania": {
        "wm42-n1-six": MatchResultSchema(winner_side="left"),
        "wm42-n1-unsanctioned": MatchResultSchema(winner_side="left", winner_name="Jacob Fatu"),
        "wm42-n1-women-tag": MatchResultSchema(winner_index=0),
        "wm42-n1-women-ic": MatchResultSchema(winner_side="left", winner_name="Becky Lynch"),
        "wm42-n1-gunther-rollins": MatchResultSchema(winner_side="left", winner_name="Gunther"),
        "wm42-n1-women-world": MatchResultSchema(winner_side="left", winner_name="Liv Morgan"),
        "wm42-n1-undisputed": MatchResultSchema(winner_side="left", winner_name="Cody Rhodes"),
        "wm42-n2-femi-lesnar": MatchResultSchema(winner_side="left", winner_name="Oba Femi"),
        "wm42-n2-ic-ladder": MatchResultSchema(winner_index=0, winner_name="Penta"),
        "wm42-n2-us": MatchResultSchema(winner_side="left", winner_name="Trick Williams"),
        "wm42-n2-street": MatchResultSchema(winner_side="left", winner_name="Finn Bálor"),
        "wm42-n2-women": MatchResultSchema(winner_side="left", winner_name="Rhea Ripley"),
        "wm42-n2-whc": MatchResultSchema(winner_side="left", winner_name="Roman Reigns"),
    },
    "backlash": {
        "bl26-danhausen": MatchResultSchema(winner_side="left"),
        "bl26-iyo-asuka": MatchResultSchema(winner_side="left", winner_name="IYO SKY"),
        "bl26-us": MatchResultSchema(winner_side="left", winner_name="Trick Williams"),
        "bl26-breakker-rollins": MatchResultSchema(winner_side="left", winner_name="Bron Breakker"),
        "bl26-whc": MatchResultSchema(winner_side="left", winner_name="Roman Reigns"),
    },
}

FINISHED_2026_SLUGS = frozenset(FINISHED_2026_RESULTS.keys())


class PleService:
    def __init__(self, db: AsyncSession) -> None:
        self.ple_repository = PleRepository(db)

    @staticmethod
    def build_sync_payload(
        slug: str,
        matches: list[dict[str, Any]],
        *,
        year: int = 2026,
        status: str | None = None,
    ) -> PleEventSyncSchema:
        meta = PLE_EVENT_META.get(slug)
        if meta is None:
            raise ValueError(f"Unknown PLE slug: {slug}")

        enriched: list[dict[str, Any]] = []
        results = FINISHED_2026_RESULTS.get(slug, {})
        for card in matches:
            item = dict(card)
            if slug in FINISHED_2026_SLUGS and card["id"] in results and "result" not in item:
                item["result"] = results[card["id"]].model_dump(by_alias=True)
            enriched.append(item)

        event_status = status
        if event_status is None and slug in FINISHED_2026_SLUGS:
            event_status = PleEventStatus.FINISHED

        return PleEventSyncSchema(
            slug=slug,
            label=meta["label"],
            month=meta["month"],
            year=year,
            status=event_status,
            matches=enriched,
        )

    async def sync_event(self, payload: PleEventSyncSchema) -> PleBoardSchema:
        logger.info(
            "[PleService] sync_event -> Repository — slug=%s matches=%d",
            payload.slug,
            len(payload.matches),
        )
        event = await self.ple_repository.upsert_event_from_sync(payload)
        if payload.slug in FINISHED_2026_SLUGS and event.status != PleEventStatus.FINISHED:
            event.status = PleEventStatus.FINISHED
            event.finished_at = datetime.now(timezone.utc)
            await self.ple_repository.db.flush()
        board = await self.get_board(payload.slug)
        logger.info("[PleService] sync_event <- Repository — slug=%s", payload.slug)
        return board

    async def sync_event_from_cards(
        self,
        slug: str,
        matches: list[dict[str, Any]],
        *,
        year: int = 2026,
        status: str | None = None,
    ) -> PleBoardSchema:
        payload = self.build_sync_payload(slug, matches, year=year, status=status)
        return await self.sync_event(payload)

    async def sync_all_from_cards(
        self, catalog: dict[str, list[dict[str, Any]]], *, year: int = 2026
    ) -> list[PleEventSummarySchema]:
        summaries: list[PleEventSummarySchema] = []
        for slug in PLE_EVENT_META:
            if slug not in catalog:
                continue
            await self.sync_event_from_cards(slug, catalog[slug], year=year)
            board = await self.get_board(slug)
            summaries.append(
                PleEventSummarySchema(
                    slug=board.slug,
                    label=board.label,
                    month=board.month,
                    year=board.year,
                    status=board.status,
                    match_count=len(board.matches),
                )
            )
        return summaries

    async def get_board(self, slug: str, *, client_id: str | None = None) -> PleBoardSchema:
        event = await self.ple_repository.get_event_by_slug(slug)
        if event is None:
            raise LookupError(slug)

        matches_out: list[MatchBoardSchema] = []
        for row in sorted(event.matches, key=lambda m: m.sort_order):
            card = json.loads(row.card_json)
            vote_raw, _ = self.ple_repository.aggregate_votes(row)
            my_pick: str | None = None
            if client_id:
                pred = await self.ple_repository.get_prediction(row.id, client_id)
                if pred:
                    my_pick = pred.pick

            result = None
            if row.winner_pick or row.winner_name:
                if row.format == "multi":
                    try:
                        result = MatchResultSchema(
                            winner_index=int(row.winner_pick) if row.winner_pick else None,
                            winner_name=row.winner_name,
                        )
                    except ValueError:
                        result = MatchResultSchema(winner_name=row.winner_name)
                else:
                    result = MatchResultSchema(
                        winner_side=row.winner_pick
                        if row.winner_pick in ("left", "right")
                        else None,
                        winner_name=row.winner_name,
                    )

            matches_out.append(
                MatchBoardSchema(
                    id=row.match_key,
                    db_id=row.id,
                    title=row.title,
                    card_variant=row.card_variant,
                    format=row.format,
                    left=CompetitorSchema.model_validate(card["left"])
                    if card.get("left")
                    else None,
                    right=CompetitorSchema.model_validate(card["right"])
                    if card.get("right")
                    else None,
                    competitors=[
                        CompetitorSchema.model_validate(c)
                        for c in card.get("competitors") or []
                    ]
                    or None,
                    bookmaker_decimal=card.get("bookmakerDecimal"),
                    status=row.status,
                    result=result,
                    site_votes=VoteTotalsSchema(
                        left=int(vote_raw.get("left", 0)),
                        right=int(vote_raw.get("right", 0)),
                        multi=list(vote_raw.get("multi") or []),
                    ),
                    locked=my_pick is not None,
                    my_pick=my_pick,
                )
            )

        return PleBoardSchema(
            slug=event.slug,
            label=event.label,
            month=event.month,
            year=event.year,
            status=event.status,
            finished_at=event.finished_at,
            matches=matches_out,
            updated_at=event.updated_at,
        )

    async def list_events(self) -> list[PleEventSummarySchema]:
        events = await self.ple_repository.list_events()
        return [
            PleEventSummarySchema(
                slug=e.slug,
                label=e.label,
                month=e.month,
                year=e.year,
                status=e.status,
                match_count=len(e.matches),
            )
            for e in events
        ]

    async def record_prediction(
        self,
        slug: str,
        match_key: str,
        body: PredictionRequestSchema,
        user_id: int | None = None,
    ) -> PleBoardSchema:
        event = await self.ple_repository.get_event_by_slug(slug)
        if event is None:
            raise LookupError(slug)
        match = next((m for m in event.matches if m.match_key == match_key), None)
        if match is None:
            raise LookupError(match_key)
        if match.status == PleMatchStatus.FINISHED:
            raise ValueError("종료된 경기에는 예측할 수 없습니다.")
        existing = await self.ple_repository.get_prediction(match.id, body.client_id)
        if existing:
            return await self.get_board(slug, client_id=body.client_id)

        logger.info(
            "[PleService] record_prediction -> Repository — slug=%s match=%s client=%s pick=%s",
            slug,
            match_key,
            body.client_id,
            body.pick,
        )
        await self.ple_repository.add_prediction(
            match.id, body.client_id, body.pick, user_id
        )
        return await self.get_board(slug, client_id=body.client_id)

    async def set_match_result(
        self,
        slug: str,
        match_key: str,
        body: MatchResultUpdateSchema,
    ) -> PleBoardSchema:
        result = MatchResultSchema(
            winner_side=body.winner_side,
            winner_index=body.winner_index,
            winner_name=body.winner_name,
        )
        row = await self.ple_repository.set_match_result(
            slug, match_key, result, status=body.status
        )
        if row is None:
            raise LookupError(match_key)
        return await self.get_board(slug)

    async def finalize_event(self, slug: str) -> PleBoardSchema:
        event = await self.ple_repository.finalize_event(slug)
        if event is None:
            raise LookupError(slug)
        return await self.get_board(slug)
