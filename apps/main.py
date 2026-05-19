import asyncio
import json
import logging
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import Depends, FastAPI, HTTPException
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.db_health_adapter import DbHealthAdapter
from database import (
    AsyncSessionLocal,
    configure_db_logging,
    dispose_engine,
    get_db,
    init_db,
)
from doro.app.doro_director import DoroDirector
from matrix.app.keymaker import get_keymaker
from secom.app.models.role import UserRole
from secom.app.schemas.user_schema import UserSchema
from secom.app.controllers.user_controller import UserController
from titanic.app.james_controller import JamesController
from kayfabe.app.controllers.ple_controller import PleController
from kayfabe.app.schemas.ple_schema import (
    MatchResultUpdateSchema,
    PleBoardSchema,
    PleEventSummarySchema,
    PleEventSyncSchema,
    PredictionRequestSchema,
)
keymaker = get_keymaker()
logger = logging.getLogger("uvicorn.error")


class ChatRequest(BaseModel):
    """채팅 요청 본문. 사용자 메시지를 JSON으로 전달합니다."""

    message: str = Field(..., min_length=1, description="사용자 메시지")


class ChatResponse(BaseModel):
    reply: str


class SeoulWeatherResponse(BaseModel):
    city: str
    temp_c: float
    description: str
    condition_id: int


class SignupRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId", min_length=1, description="회원가입 ID")
    nickname: str = Field(..., min_length=1, description="회원가입 닉네임")
    email: str = Field(..., min_length=1, description="회원가입 이메일")
    password: str = Field(..., min_length=1, description="회원가입 비밀번호")
    password_confirm: str = Field(
        ...,
        alias="passwordConfirm",
        min_length=1,
        description="회원가입 비밀번호 확인",
    )


class SignupResponse(BaseModel):
    message: str
    nickname: str
    email: str
    role: UserRole


class LoginRequest(BaseModel):
    model_config = ConfigDict(populate_by_name=True)

    user_id: str = Field(..., alias="userId", min_length=1, description="로그인 ID")
    password: str = Field(..., min_length=1, description="로그인 비밀번호")


class LoginResponse(BaseModel):
    message: str
    nickname: str
    email: str
    role: UserRole


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_db_logging()
    try:
        await init_db()
        yield
    finally:
        await dispose_engine()


app = FastAPI(title="Jsangho Main Page", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"message": "FAST API 메인 페이지 ", "docs": "/docs"}

@app.post("/chat", response_model=ChatResponse)
def chat(req: ChatRequest) -> ChatResponse:
    """
    JSON 본문 `{"message": "..."}` 를 받아 Gemini 답변 문자열을 반환합니다.
    """
    if not keymaker.is_gemini_ready():
        if not keymaker.get_gemini_api_key():
            raise HTTPException(
                status_code=503,
                detail="GEMINI_API_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요.",
            )
        raise HTTPException(
            status_code=503,
            detail=(
                "Gemini 패키지가 설치되지 않았습니다. "
                "backend 폴더에서 `pip install -r requirements.txt` 후 서버를 재시작하세요."
            ),
        )

    model = keymaker.get_gemini_model()
    try:
        response = model.generate_content(req.message)
    except Exception as e:
        err = str(e)
        if "429" in err or "quota" in err.lower() or "ResourceExhausted" in type(e).__name__:
            raise HTTPException(
                status_code=429,
                detail=(
                    "Gemini API 무료 할당량을 초과했거나, 이 프로젝트에 무료 할당량이 "
                    "활성화되지 않았습니다(limit: 0). "
                    "1~2분 후 다시 시도하거나, "
                    "https://aistudio.google.com/apikey 에서 새 키를 발급하고 "
                    "https://ai.dev/rate-limit 에서 사용량을 확인하세요. "
                    "계속되면 Google AI Studio에서 결제(빌링) 연결 후 무료 한도가 켜집니다."
                ),
            ) from e
        raise HTTPException(
            status_code=502,
            detail=f"Gemini 호출 실패: {e!s}",
        ) from e

    try:
        text = (response.text or "").strip()
    except ValueError as e:
        feedback = getattr(response, "prompt_feedback", None)
        raise HTTPException(
            status_code=400,
            detail=f"응답 텍스트를 읽을 수 없습니다: {e!s}. prompt_feedback={feedback}",
        ) from e

    if not text:
        reason = None
        if getattr(response, "candidates", None):
            c0 = response.candidates[0]
            reason = getattr(c0, "finish_reason", None)
        raise HTTPException(
            status_code=502,
            detail=(
                "모델이 비어 있는 응답을 반환했습니다."
                + (f" (finish_reason={reason})" if reason else "")
            ),
        )

    return ChatResponse(reply=text)


@app.get("/weather/seoul", response_model=SeoulWeatherResponse)
def read_seoul_weather() -> SeoulWeatherResponse:
    """OpenWeatherMap으로 서울 현재 기온·날씨를 조회합니다 (`OPENWEATHER_API_KEY`)."""
    if not keymaker.is_openweather_ready():
        raise HTTPException(
            status_code=503,
            detail="OPENWEATHER_API_KEY가 설정되지 않았습니다. backend/.env 에 키를 넣어 주세요.",
        )
    try:
        data = keymaker.get_seoul_current_weather()
    except ValueError as e:
        raise HTTPException(status_code=503, detail=str(e)) from e
    except RuntimeError as e:
        raise HTTPException(status_code=502, detail=str(e)) from e
    return SeoulWeatherResponse(**data)


@app.get("/db-check")
async def check_db(db: AsyncSession = Depends(get_db)):
    return await DbHealthAdapter.neon_time_check(db)


@app.get("/titanic/data")
def read_titanic_data():
    james = JamesController()
    df = james.get_data()

    return df.to_dict(orient="records")


@app.get("/titanic/count")
def read_titanic_count():
    james = JamesController()
    count = james.get_count()

    return {"count": count}

@app.get("/titanic/tree")
def read_titanic_tree():
    james = JamesController()
    tree = james.has_decision_tree_model()

    return {"tree": tree}


@app.get("/titanic/model")
def read_titanic_model():
    controller = JamesController()
    model_name = controller.get_model_name_and_accuracy()
    return JSONResponse(content=jsonable_encoder(model_name))


@app.get("/doro/data")
def read_doro_data():
    doro_director = DoroDirector()
    df = doro_director.get_data()

    return df.to_dict(orient="records")

#회원가입
@app.post("/signup", response_model=SignupResponse)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    logger.info("[API] signup 요청 — userId=%s", req.user_id)

    user_schema = UserSchema(
        login_id=req.user_id.strip(),
        nickname=req.nickname,
        email=req.email,
        password=req.password,
        password_confirm=req.password_confirm,
        role=UserRole.USER,
    )

    user_controller = UserController(db)
    await user_controller.save_user(user_schema)

    return SignupResponse(
        message="회원가입이 완료되었습니다.",
        nickname=req.nickname,
        email=req.email,
        role=UserRole.USER,
    )


@app.get("/ple", response_model=list[PleEventSummarySchema])
async def list_ple_events(db: AsyncSession = Depends(get_db)):
    return await PleController(db).list_events()


@app.get("/ple/{slug}", response_model=PleBoardSchema, response_model_by_alias=True)
async def get_ple_board(
    slug: str,
    client_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await PleController(db).get_board(slug, client_id=client_id)
    except LookupError:
        raise HTTPException(status_code=404, detail="PLE not found") from None


@app.post("/ple/sync", response_model=PleBoardSchema, response_model_by_alias=True)
async def sync_ple_event(payload: PleEventSyncSchema, db: AsyncSession = Depends(get_db)):
    return await PleController(db).sync_event(payload)


@app.post(
    "/ple/{slug}/sync-from-client",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def sync_ple_from_client_cards(
    slug: str,
    payload: PleEventSyncSchema,
    db: AsyncSession = Depends(get_db),
):
    if payload.slug != slug:
        raise HTTPException(status_code=400, detail="slug in path and body must match")
    return await PleController(db).sync_event(payload)


@app.post(
    "/ple/{slug}/matches/{match_key}/predict",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def ple_predict(
    slug: str,
    match_key: str,
    body: PredictionRequestSchema,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await PleController(db).predict(slug, match_key, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="PLE or match not found") from None
    except ValueError as e:
        raise HTTPException(status_code=409, detail=str(e)) from e


@app.patch(
    "/ple/{slug}/matches/{match_key}/result",
    response_model=PleBoardSchema,
    response_model_by_alias=True,
)
async def ple_set_result(
    slug: str,
    match_key: str,
    body: MatchResultUpdateSchema,
    db: AsyncSession = Depends(get_db),
):
    try:
        return await PleController(db).set_result(slug, match_key, body)
    except LookupError:
        raise HTTPException(status_code=404, detail="PLE or match not found") from None


@app.post("/ple/{slug}/finalize", response_model=PleBoardSchema, response_model_by_alias=True)
async def ple_finalize(slug: str, db: AsyncSession = Depends(get_db)):
    try:
        return await PleController(db).finalize(slug)
    except LookupError:
        raise HTTPException(status_code=404, detail="PLE not found") from None


@app.get("/ple/{slug}/live")
async def ple_live_board(slug: str, client_id: str | None = None):
    """SSE — 투표·결과 변경 시 3초 주기로 보드 스냅샷 전송."""

    if AsyncSessionLocal is None:
        raise HTTPException(
            status_code=503,
            detail="DATABASE_URL이 설정되지 않았습니다.",
        )

    async def event_stream():
        last_payload: str | None = None
        while True:
            async with AsyncSessionLocal() as session:
                try:
                    board = await PleController(session).get_board(slug, client_id=client_id)
                    await session.commit()
                except LookupError:
                    yield f"data: {json.dumps({'error': 'not_found'})}\n\n"
                    break
                except Exception as e:
                    yield f"data: {json.dumps({'error': str(e)})}\n\n"
                    await asyncio.sleep(3)
                    continue

            payload = json.dumps(
                board.model_dump(mode="json", by_alias=True),
                default=str,
            )
            if payload != last_payload:
                yield f"data: {payload}\n\n"
                last_payload = payload
            await asyncio.sleep(3)

    return StreamingResponse(
        event_stream(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


@app.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    login_id = req.user_id.strip()
    logger.info("[API] login 요청 — userId=%s", login_id)

    user_controller = UserController(db)
    user = await user_controller.login_user(login_id, req.password)

    return LoginResponse(
        message="로그인되었습니다.",
        nickname=user.nickname,
        email=user.email,
        role=UserRole(user.role),
    )


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("main:app", host="127.0.0.1", port=8000, reload=True)
