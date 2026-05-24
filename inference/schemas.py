from pydantic import BaseModel, Field
from typing import List, Literal, Optional


class Message(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class ChatRequest(BaseModel):
    messages: List[Message]
    max_new_tokens: int = Field(default=512, ge=1, le=2048)
    temperature: float = Field(default=0.85, ge=0.1, le=2.0)
    top_p: float = Field(default=0.92, ge=0.0, le=1.0)
    repetition_penalty: float = Field(default=1.1, ge=1.0, le=2.0)
    rag_context: Optional[str] = None  # Phase 2: RAG에서 주입되는 참고 문맥
