from pathlib import Path
from pydantic_settings import BaseSettings, SettingsConfigDict


_BASE_DIR = Path(__file__).parent.parent


class Settings(BaseSettings):
    # ── 모델 설정 ─────────────────────────────────────────────
    gguf_model_path: str = str(_BASE_DIR / "models" / "gemma-2-9b-it-Q4_K_M.gguf")
    n_gpu_layers: int = -1       # -1 = 전체 GPU 오프로드
    n_ctx: int = 8192            # 컨텍스트 윈도우
    n_batch: int = 512           # 배치 크기

    # ── 데이터베이스 설정 ─────────────────────────────────────
    db_path: str = str(_BASE_DIR / "data" / "chatbot.db")

    # ── 서버 설정 ─────────────────────────────────────────────
    host: str = "0.0.0.0"
    port: int = 8000
    cors_origins: list[str] = ["http://localhost:8000", "http://127.0.0.1:8000"]

    # ── Rate Limiting ─────────────────────────────────────────
    rate_limit_chat: str = "6/minute"    # /chat/stream 제한
    rate_limit_default: str = "60/minute"

    model_config = SettingsConfigDict(
        env_file=str(_BASE_DIR / ".env"),
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


settings = Settings()
