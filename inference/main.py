import asyncio
import json
import logging
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Thread
from typing import List

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse, StreamingResponse

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
from prompts import build_messages
from schemas import (
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    global gemma
    logger.info("=== 점마 뭐꼬? 서버 시작 ===")
    await init_db()
    logger.info("SQLite DB 초기화 완료")
    gemma = GemmaInference.get_instance()
    yield
    logger.info("=== 서버 종료 ===")


app = FastAPI(
    title="점마 뭐꼬? — 웹소설/시나리오 창작 챗봇",
    version="1.0.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
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
    return {
        "status": "ok",
        "model": "gemma-2-9b-it-AWQ",
        "model_loaded": gemma is not None,
    }


# ──────────────────────────────────────────────────────────────
# 세션 CRUD
# ──────────────────────────────────────────────────────────────

@app.post("/sessions", response_model=SessionResponse, tags=["Sessions"])
async def new_session(body: SessionCreate):
    """새 대화 세션 생성"""
    return await create_session(body.title)


@app.get("/sessions", response_model=List[SessionResponse], tags=["Sessions"])
async def list_sessions():
    """모든 세션 목록 (최신순)"""
    return await get_sessions()


@app.get("/sessions/{session_id}/messages", response_model=List[MessageResponse], tags=["Sessions"])
async def get_messages(session_id: str):
    """특정 세션의 메시지 전체 조회"""
    if not await session_exists(session_id):
        raise HTTPException(status_code=404, detail="세션을 찾을 수 없습니다.")
    return await get_session_messages(session_id)


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
# 스트리밍 채팅 엔드포인트
# ──────────────────────────────────────────────────────────────

@app.post("/chat/stream")
async def chat_stream(request: ChatRequest):
    """
    SSE(Server-Sent Events) 스트리밍 응답.
    프론트에서 fetch + ReadableStream으로 수신합니다.

    request.messages 형식:
      [{"role": "user", "content": "..."}, {"role": "assistant", "content": "..."}, ...]
    마지막 항목이 현재 사용자 메시지입니다.
    """
    if gemma is None:
        raise HTTPException(status_code=503, detail="모델이 아직 로딩 중입니다.")

    # 히스토리와 현재 메시지 분리
    history = [m.model_dump() for m in request.messages[:-1]]
    current_user_msg = request.messages[-1].content

    # 시스템 프롬프트 + RAG 컨텍스트 주입
    messages = build_messages(
        history=history,
        user_message=current_user_msg,
        rag_context=request.rag_context,
    )

    loop = asyncio.get_event_loop()
    queue: asyncio.Queue[str | None] = asyncio.Queue()

    def produce():
        """백그라운드 스레드: 토큰 생성 후 asyncio Queue에 푸시"""
        try:
            for token in gemma.stream_generate(
                messages=messages,
                max_new_tokens=request.max_new_tokens,
                temperature=request.temperature,
                top_p=request.top_p,
                repetition_penalty=request.repetition_penalty,
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


# ──────────────────────────────────────────────────────────────
# Phase 2 예약: RAG 문서 업로드 (LangChain + ChromaDB)
# ──────────────────────────────────────────────────────────────

@app.post("/rag/upload", tags=["RAG (Phase 2)"])
async def rag_upload():
    """
    [Phase 2] 웹소설 원고 / 세계관 설정집 업로드 → ChromaDB 벡터 인덱싱
    현재는 미구현 (Phase 2에서 LangChain + ChromaDB로 활성화 예정)
    """
    return {"message": "Phase 2에서 구현 예정입니다."}


@app.post("/rag/search", tags=["RAG (Phase 2)"])
async def rag_search():
    """
    [Phase 2] 쿼리와 관련된 문맥 검색 → /chat/stream의 rag_context로 주입
    """
    return {"message": "Phase 2에서 구현 예정입니다."}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=False)
