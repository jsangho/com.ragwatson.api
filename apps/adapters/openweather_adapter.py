"""OpenWeatherMap — Keymaker 위임 어댑터 (라우트 ↔ 키·API 호출)."""

from __future__ import annotations

from typing import Any

from matrix.app.keymaker import get_keymaker


class OpenWeatherAdapter:
    """HTTP 라우트용: 실제 키·호출은 `Keymaker`가 담당합니다."""

    @classmethod
    def get_seoul_current(cls) -> dict[str, Any]:
        return get_keymaker().get_seoul_current_weather()
