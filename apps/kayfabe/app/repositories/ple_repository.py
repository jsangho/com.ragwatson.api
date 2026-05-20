from __future__ import annotations

from typing import Any

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from kayfabe.app.models.ple_model import PleMatchModel, PleModel, PlePredictionModel
from kayfabe.app.models.result_model import PleResultModel

logger = LAYER_LOG


class PleRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def db_now(self):
        """
        DB 기준 현재 시각(UTC, timezone-aware)을 반환합니다.
        앱 서버/로컬 시간 오차로 event_at 판정이 흔들리지 않게 합니다.
        """
        return await self.db.scalar(select(func.now()))

    async def get_ple_by_slug(self, slug: str) -> PleModel | None:
        result = await self.db.execute(select(PleModel).where(PleModel.slug == slug))
        return result.scalar_one_or_none()

    async def upsert_ple(self, slug: str, label: str, month: int, year: int, description: str) -> PleModel:
        ple = await self.get_ple_by_slug(slug)
        if ple is None:
            ple = PleModel(slug=slug, label=label, month=month, year=year, description=description)
            self.db.add(ple)
            await self.db.flush()
            await self.db.refresh(ple)
            return ple

        ple.label = label
        ple.month = month
        ple.year = year
        ple.description = description
        await self.db.flush()
        await self.db.refresh(ple)
        return ple

    async def list_matches(self, ple_id: int) -> list[PleMatchModel]:
        result = await self.db.execute(
            select(PleMatchModel).where(PleMatchModel.ple_id == ple_id).order_by(PleMatchModel.id.asc())
        )
        return list(result.scalars().all())

    async def get_ple_result(self, ple_id: int) -> PleResultModel | None:
        result = await self.db.execute(
            select(PleResultModel).where(PleResultModel.ple_id == ple_id)
        )
        return result.scalar_one_or_none()

    async def upsert_ple_result(
        self, ple_id: int, status: str, finished_at: datetime | None
    ) -> PleResultModel:
        current = await self.get_ple_result(ple_id)
        if current is None:
            current = PleResultModel(ple_id=ple_id, status=status, finished_at=finished_at)
            self.db.add(current)
            await self.db.flush()
            await self.db.refresh(current)
            return current

        current.status = status
        current.finished_at = finished_at
        await self.db.flush()
        await self.db.refresh(current)
        return current

    async def get_match(self, ple_id: int, match_key: str) -> PleMatchModel | None:
        result = await self.db.execute(
            select(PleMatchModel).where(
                PleMatchModel.ple_id == ple_id,
                PleMatchModel.match_key == match_key,
            )
        )
        return result.scalar_one_or_none()

    async def upsert_match(
        self,
        ple_id: int,
        match_key: str,
        title: str,
        card_variant: str,
        fmt: str,
        left: dict | None,
        right: dict | None,
        competitors: list[dict] | None,
        bookmaker_decimal: Any | None,
        status: str = "upcoming",
    ) -> PleMatchModel:
        match = await self.get_match(ple_id, match_key)
        if match is None:
            match = PleMatchModel(
                ple_id=ple_id,
                match_key=match_key,
                title=title,
                card_variant=card_variant,
                format=fmt,
                status=status,
                left=left,
                right=right,
                competitors=competitors,
                bookmaker_decimal=bookmaker_decimal,
            )
            self.db.add(match)
            await self.db.flush()
            await self.db.refresh(match)
            return match

        match.title = title
        match.card_variant = card_variant
        match.format = fmt
        match.left = left
        match.right = right
        match.competitors = competitors
        match.bookmaker_decimal = bookmaker_decimal
        await self.db.flush()
        await self.db.refresh(match)
        return match

    async def get_prediction(self, ple_match_id: int, client_id: str) -> PlePredictionModel | None:
        result = await self.db.execute(
            select(PlePredictionModel).where(
                PlePredictionModel.ple_match_id == ple_match_id,
                PlePredictionModel.client_id == client_id,
            )
        )
        return result.scalar_one_or_none()

    async def create_prediction(self, ple_match_id: int, client_id: str, pick: str) -> PlePredictionModel:
        pred = PlePredictionModel(ple_match_id=ple_match_id, client_id=client_id, pick=pick)
        self.db.add(pred)
        await self.db.flush()
        await self.db.refresh(pred)
        return pred

    async def set_match_result(
        self,
        ple_match_id: int,
        result_pick: str,
        winner_name: str | None,
    ) -> None:
        await self.db.execute(
            update(PleMatchModel)
            .where(PleMatchModel.id == ple_match_id)
            .values(
                status="finished",
                result_pick=result_pick,
                result_winner=winner_name,
            )
        )
        await self.db.flush()

    async def mark_predictions_correctness(self, ple_match_id: int, correct_pick: str) -> None:
        # 모든 예측에 대해 pick==correct_pick 이면 True, 아니면 False
        preds = await self.db.execute(
            select(PlePredictionModel).where(PlePredictionModel.ple_match_id == ple_match_id)
        )
        for p in preds.scalars().all():
            p.is_correct = p.pick == correct_pick
        await self.db.flush()

    async def count_votes_singles(self, ple_match_id: int) -> dict[str, int]:
        left_count = await self.db.scalar(
            select(func.count()).select_from(PlePredictionModel).where(
                PlePredictionModel.ple_match_id == ple_match_id,
                PlePredictionModel.pick == "left",
            )
        )
        right_count = await self.db.scalar(
            select(func.count()).select_from(PlePredictionModel).where(
                PlePredictionModel.ple_match_id == ple_match_id,
                PlePredictionModel.pick == "right",
            )
        )
        return {"left": int(left_count or 0), "right": int(right_count or 0)}

    async def count_votes_multi(self, ple_match_id: int, competitor_count: int) -> list[int]:
        rows = await self.db.execute(
            select(PlePredictionModel.pick, func.count()).where(
                PlePredictionModel.ple_match_id == ple_match_id
            ).group_by(PlePredictionModel.pick)
        )
        counts: list[int] = [0 for _ in range(max(0, competitor_count))]
        for pick, cnt in rows.all():
            try:
                idx = int(pick)
            except Exception:
                continue
            if 0 <= idx < len(counts):
                counts[idx] = int(cnt)
        return counts