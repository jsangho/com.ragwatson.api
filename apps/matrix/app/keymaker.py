"""시스템 전역 API 키·환경 변수·외부 클라이언트(Gemini, OpenWeather 등)를 한곳에서 관리합니다."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import urlopen

SEOUL_LAT = 37.5665
SEOUL_LON = 126.978
OPENWEATHER_CURRENT_URL = "https://api.openweathermap.org/data/2.5/weather"


def default_backend_env_path() -> Path:
    """`backend/.env` — 이 파일: `apps/matrix/app/keymaker.py` 기준."""
    return Path(__file__).resolve().parent.parent.parent.parent / ".env"


class Keymaker:
    """
    전역 키·설정 관리자.

    - `backend/.env` 로드
    - Gemini API 키 및 `GenerativeModel` 인스턴스 보관
    - OpenWeatherMap API 키 및 서울 날씨 조회
    """

    _instance: Keymaker | None = None

    def __init__(self, env_path: Path | None = None) -> None:
        self._env_path = env_path or default_backend_env_path()
        self._dotenv_loaded = False
        self._gemini_model: Any = None
        self._gemini_model_id = "gemini-2.5-flash"

    @classmethod
    def instance(cls, env_path: Path | None = None) -> Keymaker:
        """프로세스당 하나의 Keymaker (첫 생성 시 env_path만 적용)."""
        if cls._instance is None:
            cls._instance = cls(env_path=env_path)
        return cls._instance

    @classmethod
    def reset_instance(cls) -> None:
        """테스트 등에서 인스턴스를 비울 때만 사용."""
        cls._instance = None

    def load_env(self) -> None:
        """`.env`를 한 번만 로드하고, Gemini 클라이언트를 준비합니다."""
        if not self._dotenv_loaded:
            from dotenv import load_dotenv

            load_dotenv(self._env_path, override=True)
            self._dotenv_loaded = True
        if self._gemini_model is None:
            self._bootstrap_gemini()

    def _resolve_gemini_model_id(self) -> str:
        model = (os.getenv("GEMINI_MODEL") or "gemini-2.5-flash").strip()
        return model or "gemini-2.5-flash"

    def _bootstrap_gemini(self) -> None:
        key = (os.getenv("GEMINI_API_KEY") or "").strip()
        if not key:
            self._gemini_model = None
            return
        try:
            import google.generativeai as genai
        except ModuleNotFoundError:
            self._gemini_model = None
            return
        self._gemini_model_id = self._resolve_gemini_model_id()
        genai.configure(api_key=key)
        self._gemini_model = genai.GenerativeModel(self._gemini_model_id)

    def get_secret(self, name: str, default: str = "") -> str:
        """임의 환경 변수(민감 값) 조회. 필요 시 `.env` 로드를 트리거합니다."""
        self.load_env()
        return (os.getenv(name) or default).strip()

    def get_gemini_api_key(self) -> str:
        self.load_env()
        return (os.getenv("GEMINI_API_KEY") or "").strip()

    def get_gemini_model_name(self) -> str:
        return self._gemini_model_id

    def get_gemini_model(self) -> Any:
        """설정된 경우 `google.generativeai.GenerativeModel`, 없으면 `None`."""
        self.load_env()
        return self._gemini_model

    def is_gemini_ready(self) -> bool:
        self.load_env()
        return self._gemini_model is not None

    # --- OpenWeatherMap ---

    def get_openweather_api_key(self) -> str:
        self.load_env()
        return (os.getenv("OPENWEATHER_API_KEY") or "").strip()

    def is_openweather_ready(self) -> bool:
        return bool(self.get_openweather_api_key())

    def _fetch_openweather_current(self, lat: float, lon: float) -> dict[str, Any]:
        api_key = self.get_openweather_api_key()
        if not api_key:
            raise ValueError(
                "OPENWEATHER_API_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요."
            )

        query = urlencode(
            {
                "lat": lat,
                "lon": lon,
                "appid": api_key,
                "units": "metric",
                "lang": "kr",
            }
        )
        url = f"{OPENWEATHER_CURRENT_URL}?{query}"

        try:
            with urlopen(url, timeout=10) as resp:
                data = json.loads(resp.read().decode())
        except HTTPError as e:
            body = e.read().decode(errors="replace") if e.fp else ""
            raise RuntimeError(f"OpenWeather HTTP {e.code}: {body}") from e
        except URLError as e:
            raise RuntimeError(f"OpenWeather 연결 실패: {e.reason}") from e

        main = data.get("main") or {}
        weather_list = data.get("weather") or []
        condition = weather_list[0] if weather_list else {}

        temp = main.get("temp")
        condition_id = condition.get("id")
        if temp is None or condition_id is None:
            raise RuntimeError("OpenWeather 응답 형식이 올바르지 않습니다.")

        return {
            "city": data.get("name") or "",
            "temp_c": round(float(temp), 1),
            "description": condition.get("description") or "",
            "condition_id": int(condition_id),
        }

    def get_seoul_current_weather(self) -> dict[str, Any]:
        """서울(기본 좌표) 현재 기온·날씨를 OpenWeatherMap에서 조회합니다."""
        result = self._fetch_openweather_current(SEOUL_LAT, SEOUL_LON)
        if not result["city"]:
            result["city"] = "Seoul"
        return result


def get_keymaker(env_path: Path | None = None) -> Keymaker:
    """애플리케이션 전역에서 사용할 Keymaker 싱글톤."""
    return Keymaker.instance(env_path=env_path)
