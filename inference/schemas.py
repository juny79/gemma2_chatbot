from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str = Field(..., min_length=1, max_length=10_000)


class ChatRequest(BaseModel):
    messages: List[Message] = Field(..., min_length=1)
    max_new_tokens: int = Field(default=2048, ge=1, le=4096)
    temperature: float = Field(default=0.85, ge=0.1, le=2.0)
    top_p: float = Field(default=0.92, ge=0.0, le=1.0)
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    rag_context: Optional[str] = Field(default=None, max_length=20_000)  # Phase 2: RAG에서 주입되는 참고 문맥


# ── 세션 관련 스키마 ─────────────────────────────────────

class SessionCreate(BaseModel):
    title: str = Field(default="새 대화", min_length=1, max_length=100)


class SessionTitleUpdate(BaseModel):
    title: str = Field(..., min_length=1, max_length=100)


class SessionResponse(BaseModel):
    id: str
    title: str
    created_at: str
    updated_at: str


class MessageResponse(BaseModel):
    id: int
    session_id: str
    role: str
    content: str
    created_at: str


class SaveMessagesRequest(BaseModel):
    messages: List[Message] = Field(..., min_length=1)


# ── 자동 제목 생성 ────────────────────────────────────────

class AutoTitleRequest(BaseModel):
    first_user_message: str = Field(..., min_length=1, max_length=2000)
