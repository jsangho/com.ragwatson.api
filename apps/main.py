import asyncio
import json
import logging
import os
import sys
from contextlib import asynccontextmanager

if sys.platform == "win32":
    # Anaconda(numpy/scipy) + uvicorn --reload 종료 시 forrtl error (200) 방지
    os.environ.setdefault("FOR_DISABLE_CONSOLE_CTRL_HANDLER", "1")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.encoders import jsonable_encoder
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.ext.asyncio import AsyncSession

from adapters.db_health_adapter import DbHealthAdapter
from database import (
    AsyncSessionLocal,
    attach_neon_sql_logging,
    configure_db_logging,
    dispose_engine,
    engine,
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
from kayfabe.app.schemas.ple_schema import PleBoard, PredictRequest, SetResultRequest, SyncFromClientRequest
from kayfabe.app.controllers.result_controller import ResultController
from kayfabe.app.schemas.result_schema import PleResultsResponse

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
    if engine is not None:
        attach_neon_sql_logging(engine)
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


@app.middleware("http")
async def log_auth_requests(request: Request, call_next):
    """로그인·회원가입 요청이 들어오면 uvicorn 터미널에 먼저 표시합니다."""
    if request.url.path in ("/login", "/signup") and request.method == "POST":
        logger.info("[API] %s %s", request.method, request.url.path)
    return await call_next(request)


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


@app.get("/ple/{slug}", response_model=PleBoard)
async def get_ple_board(
    slug: str,
    client_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    controller = PleController(db)
    try:
        return await controller.get_board(slug, client_id=client_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="PLE not found")


@app.post("/ple/{slug}/sync-from-client", response_model=PleBoard)
async def sync_ple_from_client(
    slug: str,
    req: SyncFromClientRequest,
    db: AsyncSession = Depends(get_db),
):
    payload = req.model_copy(update={"slug": slug})
    controller = PleController(db)
    return await controller.sync_from_client(payload)


@app.post("/ple/{slug}/matches/{match_key}/predict", response_model=PleBoard)
async def predict_ple_match(
    slug: str,
    match_key: str,
    req: PredictRequest,
    db: AsyncSession = Depends(get_db),
):
    controller = PleController(db)
    try:
        return await controller.predict(
            slug=slug,
            match_key=match_key,
            client_id=req.clientId,
            pick=req.pick,
        )
    except KeyError:
        raise HTTPException(status_code=404, detail="PLE not found")


@app.post("/ple/{slug}/matches/{match_key}/result", response_model=PleBoard)
async def set_ple_match_result(
    slug: str,
    match_key: str,
    req: SetResultRequest,
    db: AsyncSession = Depends(get_db),
):
    controller = PleController(db)
    try:
        return await controller.set_result(slug, match_key, req)
    except KeyError:
        raise HTTPException(status_code=404, detail="PLE not found")
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/ple/{slug}/live")
async def ple_live(
    slug: str,
    client_id: str | None = None,
    db: AsyncSession = Depends(get_db),
):
    controller = PleController(db)

    async def gen():
        try:
            async for chunk in controller.live_stream(slug, client_id):
                yield chunk
        except Exception as e:
            payload = json.dumps({"error": str(e)}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(gen(), media_type="text/event-stream")


@app.get("/results", response_model=PleResultsResponse)
async def list_ple_results(
    year: int = 2026,
    db: AsyncSession = Depends(get_db),
):
    controller = ResultController(db)
    return await controller.list_results(year)

#회원가입
@app.post("/signup", response_model=SignupResponse)
async def signup(req: SignupRequest, db: AsyncSession = Depends(get_db)):
    logger.info("[API] POST /signup — userId=%s", req.user_id)
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


@app.post("/login", response_model=LoginResponse)
async def login(req: LoginRequest, db: AsyncSession = Depends(get_db)):
    login_id = req.user_id.strip()
    logger.info("[API] POST /login — userId=%s", login_id)

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

    # Windows: --reload 시 WatchFiles가 프로세스를 끊을 때 forrtl/libifcoremd 충돌 발생
    use_reload = sys.platform != "win32"

    uvicorn.run(
        "main:app",
        host="127.0.0.1",
        port=8000,
        reload=use_reload,
        loop="asyncio",
    )
