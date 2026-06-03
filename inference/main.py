import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread
from typing import List, Optional

from fastapi import FastAPI, HTTPException, Request, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded

from config import settings
from database import (
    init_db,
    create_session,
    get_sessions,
    get_session_messages,
    session_exists,
    add_messages,
    update_session_title,
    delete_session,
)
from model import GemmaInference
from prompts import build_messages, build_auto_title_messages
from schemas import (
    AutoTitleRequest,
    ChatRequest,
    SaveMessagesRequest,
    SessionCreate,
    SessionResponse,
    SessionTitleUpdate,
    MessageResponse,
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger(__name__)

gemma: GemmaInference | None = None

FRONTEND_PATH = Path(__file__).parent.parent / "frontend" / "index.html"

# ── Rate Limiter 초기화 ───────────────────────────────────────
limiter = Limiter(key_func=get_remote_address)


@asynccontextmanager
async def lifespan(app: FastAPI):
    global gemma
    logger.info("=== 점마 뭐꼬? 서버 시작 ===")
    await init_db()
    logger.info("SQLite DB 초기화 완료 (WAL 모드)")
    gemma = GemmaInference.get_instance()
    gemma.warmup()
    yield
    logger.info("=== 서버 종료 ===")


app = FastAPI(
    title="점마 뭐꼬? — 웹소설/시나리오 창작 챗봇",
    version="1.1.0",
    lifespan=lifespan,
)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_methods=["GET", "POST", "PATCH", "DELETE"],
    allow_headers=["Content-Type"],
)


# ──────────────────────────────────────────────────────────────
# 프론트엔드 서빙
# ──────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def serve_frontend():
    if not FRONTEND_PATH.exists():
        raise HTTPException(status_code=404, detail="frontend/index.html 파일이 없습니다.")
    return FRONTEND_PATH.read_text(encoding="utf-8")


# ──────────────────────────────────────────────────────────────
# 헬스 체크
# ──────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    model_path = Path(settings.gguf_model_path)
    return {
        "status": "ok",
        "model": model_path.name,
        "model_path": str(model_path),
        "model_loaded": gemma is not None and gemma.model is not None,
        "n_ctx": settings.n_ctx,
    }


# ──────────────────────────────────────────────────────────────
# 세션 CRUD
# ──────────────────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
async def new_session(body: SessionCreate):
    """새 대화 세션 생성"""
    return await create_session(body.title)


@app.get("/sessions", response_model=List[SessionResponse], tags=["Sessions"])
async def list_sessions(q: Optional[str] = Query(default=None, max_length=100)):
    """모든 세션 목록 (최신순). q 파라미터로 제목 검색 가능."""
    return await get_sessions(q=q)


@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse], tags=["Sessions"])
async def get_messages(
    session_id: str,
    limit: int = Query(default=100, ge=1, le=500),
    offset: int = Query(default=0, ge=0),
):
    """특정 세션의 메시지 조회 (페이지네이션 지원)"""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return await get_session_messages(session_id, limit=limit, offset=offset)


@app.post("/sessions/{session_id}/messages", status_code=204, tags=["Sessions"])
async def save_messages(session_id: str, body: SaveMessagesRequest):
    """대화 교환 저장 (user + assistant 메시지 쌍)"""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    await add_messages(session_id, [m.model_dump() for m in body.messages])


@app.patch("/sessions/{session_id}/title", status_code=204, tags=["Sessions"])
async def rename_session(session_id: str, body: SessionTitleUpdate):
    """세션 제목 수정"""
    ok = await update_session_title(session_id, body.title)
    if not ok:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


@app.delete("/sessions/{session_id}", status_code=204, tags=["Sessions"])
async def remove_session(session_id: str):
    """세션 삭제 (메시지 포함)"""
    ok = await delete_session(session_id)
    if not ok:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


# ──────────────────────────────────────────────────────────────
# 자동 제목 생성
# ──────────────────────────────────────────────────────────────

@app.post("/sessions/{session_id}/auto-title", status_code=204, tags=["Sessions"])
@limiter.limit("10/minute")
async def auto_title(session_id: str, body: AutoTitleRequest, request: Request):
    """
    첫 번째 사용자 메시지를 바탕으로 LLM이 세션 제목을 자동 생성합니다.
    생성된 제목으로 세션 제목을 즉시 업데이트합니다.
    """
    if gemma is None:
        raise HTTPException(status_code=503, detail="모델이 아직 로딩 중입니다.")
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")

    messages = build_auto_title_messages(body.first_user_message)
    title_tokens: list[str] = []
    for token in gemma.stream_generate(messages=messages, max_new_tokens=30, temperature=0.3):
        title_tokens.append(token)

    raw_title = "".join(title_tokens).strip()
    # 따옴표, 줄바꿈, 마침표 제거 후 최대 50자
    title = raw_title.strip('"\'""''\n.。').strip()[:50] or body.first_user_message[:25]

    ok = await update_session_title(session_id, title)
    if not ok:
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")


# ──────────────────────────────────────────────────────────────
# 스트리밍 채팅 엔드포인트
# ──────────────────────────────────────────────────────────────

@app.post("/chat/stream")
@limiter.limit(settings.rate_limit_chat)
async def chat_stream(request: Request, body: ChatRequest):
    """
    SSE(Server-Sent Events) 스트리밍 응답.
    프론트에서 fetch + ReadableStream으로 수신합니다.

    body.messages 형식:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    마지막 항목이 현재 사용자 메시지입니다.
    """
    if gemma is None:
        raise HTTPException(status_code=503, detail="모델이 아직 로딩 중입니다.")

    # 히스토리와 현재 메시지 분리
    history = [m.model_dump() for m in body.messages[:-1]]
    current_user_msg = body.messages[-1].content

    # 시스템 프롬프트 + RAG 컨텍스트 주입
    messages = build_messages(
        history=history,
        user_message=current_user_msg,
        rag_context=body.rag_context,
    )

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def produce():
        """백그라운드 스레드: 토큰 생성 후 asyncio Queue에 푸시"""
        try:
            for token in gemma.stream_generate(
                messages=messages,
                max_new_tokens=body.max_new_tokens,
                temperature=body.temperature,
                top_p=body.top_p,
                repetition_penalty=body.repetition_penalty,
            ):
                loop.call_soon_threadsafe(queue.put_nowait, token)
        except Exception as e:
            logger.error(f"생성 오류: {e}")
            loop.call_soon_threadsafe(queue.put_nowait, f"\n\n[오류: {e}]")
        finally:
            loop.call_soon_threadsafe(queue.put_nowait, None)  # 종료 신호

    Thread(target=produce, daemon=True).start()

    async def event_generator():
        while True:
            token = await queue.get()
            if token is None:
                yield "data: [DONE]\n\n"
                break
            payload = json.dumps({"token": token}, ensure_ascii=False)
            yield f"data: {payload}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",  # Nginx 프록시 버퍼링 비활성화
        },
    )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
