from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from database import LAYER_LOG
from kayfabe.app.models.ple_model import PleModel
from kayfabe.app.models.result_model import PleResultModel

logger = LAYER_LOG


class ResultRepository:
    def __init__(self, db: AsyncSession) -> None:
        self.db = db

    async def get_ple_by_slug(self, slug: str) -> PleModel | None:
        result = await self.db.execute(select(PleModel).where(PleModel.slug == slug))
        return result.scalar_one_or_none()

    async def get_result_by_ple_id(self, ple_id: int) -> PleResultModel | None:
        result = await self.db.execute(
            select(PleResultModel).where(PleResultModel.ple_id == ple_id)
        )
        return result.scalar_one_or_none()

    async def list_results(self, year: int) -> list[tuple[PleModel, PleResultModel | None]]:
        # 결과가 없는 PLE도 함께 보여주기 위해 left join 대신 2-step으로 단순화
        ples_res = await self.db.execute(
            select(PleModel).where(PleModel.year == year).order_by(PleModel.month.asc())
        )
        ples = list(ples_res.scalars().all())
        out: list[tuple[PleModel, PleResultModel | None]] = []
        for ple in ples:
            r = await self.get_result_by_ple_id(int(ple.id or 0))
            out.append((ple, r))
        return out

