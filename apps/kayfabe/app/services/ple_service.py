from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone

from database import LAYER_LOG
from kayfabe.app.repositories.ple_repository import PleRepository
from kayfabe.app.schemas.ple_schema import (
    PleBoard,
    PleBoardMatch,
    PleMatchResult,
    SetResultRequest,
    SyncFromClientRequest,
)

logger = LAYER_LOG


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _stable_hash(text: str) -> int:
    h = 2166136261
    for ch in text:
        h ^= ord(ch)
        h = (h * 16777619) & 0xFFFFFFFF
    return h


def _is_past_ple(event_at: datetime | None) -> bool:
    if event_at is None:
        return False
    return datetime.now(timezone.utc) >= event_at


def _auto_pick_for_match(match_key: str, fmt: str, competitor_count: int) -> str:
    h = _stable_hash(match_key)
    if fmt == "multi":
        if competitor_count <= 0:
            return "0"
        return str(h % competitor_count)
    return "left" if (h % 2 == 0) else "right"


class PleService:
    def __init__(self, repo: PleRepository) -> None:
        self.repo = repo

    async def sync_from_client(self, req: SyncFromClientRequest) -> PleBoard:
        # description은 클라이언트 payload에 없을 수 있어 label로만 채움(필요 시 프론트에서 추가)
        ple = await self.repo.upsert_ple(
            slug=req.slug,
            label=req.label,
            month=req.month,
            year=req.year,
            description=req.label,
        )

        for m in req.matches:
            left = m.left.model_dump() if m.left else None
            right = m.right.model_dump() if m.right else None
            competitors = [c.model_dump() for c in (m.competitors or [])] or None
            await self.repo.upsert_match(
                ple_id=ple.id or 0,
                match_key=m.id,
                title=m.title,
                card_variant=m.cardVariant,
                fmt=m.format,
                left=left,
                right=right,
                competitors=competitors,
                bookmaker_decimal=m.bookmakerDecimal,
            )

        return await self.get_board(req.slug, client_id=None)

    async def get_board(self, slug: str, client_id: str | None) -> PleBoard:
        ple = await self.repo.get_ple_by_slug(slug)
        if ple is None:
            raise KeyError("PLE not found")

        ple_id = int(ple.id or 0)
        if ple_id <= 0:
            raise KeyError("PLE not found")

        ple_result = await self.repo.get_ple_result(ple_id)

        matches = await self.repo.list_matches(ple_id)
        board_matches: list[PleBoardMatch] = []
        status = ple_result.status if ple_result else "upcoming"
        for m in matches:
            if m.status == "finished":
                status = "finished"
            elif m.status == "live" and status != "finished":
                status = "live"

            # PLE이 이미 열린 이벤트면, 매치 결과도 자동 생성(실제 결과가 없을 때만)
            if status == "finished" and not m.result_pick:
                competitor_count = len(m.competitors or []) if m.format == "multi" else 0
                correct_pick = _auto_pick_for_match(m.match_key, m.format, competitor_count)
                if m.format == "multi":
                    winner_name = None
                    try:
                        idx = int(correct_pick)
                        winner_name = (
                            (m.competitors or [])[idx].get("name") if m.competitors else None
                        )
                    except Exception:
                        winner_name = None
                else:
                    winner_name = (
                        (m.left or {}).get("name")
                        if correct_pick == "left"
                        else (m.right or {}).get("name")
                    )
                await self.repo.set_match_result(int(m.id or 0), correct_pick, winner_name)
                await self.repo.mark_predictions_correctness(int(m.id or 0), correct_pick)
                m.result_pick = correct_pick
                m.result_winner = winner_name
                m.status = "finished"

            locked = False
            my_pick = None
            if client_id:
                pred = await self.repo.get_prediction(m.id or 0, client_id)
                if pred is not None:
                    locked = True
                    my_pick = pred.pick

            if m.format == "multi":
                competitor_count = len(m.competitors or [])
                site_votes_multi = await self.repo.count_votes_multi(m.id or 0, competitor_count)
                site_votes = {"left": 0, "right": 0, "multi": site_votes_multi}
            else:
                counts = await self.repo.count_votes_singles(m.id or 0)
                site_votes = {"left": counts["left"], "right": counts["right"], "multi": []}

            result = None
            if m.result_pick or m.result_winner:
                result = PleMatchResult(
                    winnerSide=m.result_pick if m.result_pick in ("left", "right") else None,
                    winnerIndex=int(m.result_pick) if (m.result_pick and m.result_pick.isdigit()) else None,
                    winnerName=m.result_winner,
                )

            board_matches.append(
                PleBoardMatch(
                    id=m.match_key,
                    dbId=int(m.id or 0),
                    title=m.title,
                    cardVariant=m.card_variant,  # type: ignore[arg-type]
                    format=m.format,  # type: ignore[arg-type]
                    left=m.left,
                    right=m.right,
                    competitors=m.competitors,
                    bookmakerDecimal=m.bookmaker_decimal,
                    status=m.status,
                    result=result,
                    siteVotes=site_votes,
                    locked=locked,
                    myPick=my_pick,
                )
            )

        return PleBoard(
            slug=ple.slug,
            label=ple.label,
            month=ple.month,
            year=ple.year,
            status=status,  # type: ignore[arg-type]
            finishedAt=(
                ple_result.finished_at.isoformat()
                if (ple_result and ple_result.finished_at)
                else None
            ),
            matches=board_matches,
            updatedAt=_now_iso(),
        )

    async def predict(self, slug: str, match_key: str, client_id: str, pick: str) -> PleBoard:
        ple = await self.repo.get_ple_by_slug(slug)
        if ple is None:
            raise KeyError("PLE not found")
        match = await self.repo.get_match(ple.id or 0, match_key)
        if match is None:
            raise KeyError("Match not found")

        existing = await self.repo.get_prediction(match.id or 0, client_id)
        if existing is None:
            await self.repo.create_prediction(match.id or 0, client_id, pick)

        return await self.get_board(slug, client_id=client_id)

    async def set_result(self, slug: str, match_key: str, req: SetResultRequest) -> PleBoard:
        ple = await self.repo.get_ple_by_slug(slug)
        if ple is None:
            raise KeyError("PLE not found")
        match = await self.repo.get_match(ple.id or 0, match_key)
        if match is None:
            raise KeyError("Match not found")

        correct_pick: str | None = None
        if match.format == "multi":
            if req.winnerIndex is None:
                raise ValueError("winnerIndex required for multi match")
            correct_pick = str(req.winnerIndex)
        else:
            if req.winnerSide not in ("left", "right"):
                raise ValueError("winnerSide must be left/right for singles match")
            correct_pick = req.winnerSide

        await self.repo.set_match_result(
            ple_match_id=int(match.id or 0),
            result_pick=correct_pick,
            winner_name=req.winnerName,
        )
        await self.repo.mark_predictions_correctness(
            ple_match_id=int(match.id or 0),
            correct_pick=correct_pick,
        )

        return await self.get_board(slug, client_id=None)

    async def live_stream(self, slug: str, client_id: str | None):
        """
        SSE 스트림용: 일정 주기로 보드를 다시 계산해 push.
        (현재는 DB polling 기반)
        """

        while True:
            board = await self.get_board(slug, client_id=client_id)
            payload = json.dumps(board.model_dump(), ensure_ascii=False)
            yield f"data: {payload}\n\n"
            await asyncio.sleep(2.5)