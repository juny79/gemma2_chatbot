import os
import torch
from typing import Generator
from pathlib import Path
import logging

from config import settings

logger = logging.getLogger(__name__)

# Windows에서 llama_cpp 임포트 전에 torch 번들 CUDA DLL 경로를 추가해야 함
_torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
os.add_dll_directory(_torch_lib)

from llama_cpp import Llama  # noqa: E402


class GemmaInference:
    """llama-cpp-python 기반 Gemma-2 추론 싱글턴 클래스 (CUDA GPU 오프로드)"""

    _instance: "GemmaInference | None" = None

    def __init__(self):
        self.model: Llama | None = None
        self._load()

    @classmethod
    def get_instance(cls) -> "GemmaInference":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        model_path = Path(settings.gguf_model_path)
        if not model_path.exists():
            raise FileNotFoundError(
                f"GGUF 모델 파일을 찾을 수 없습니다: {model_path}\n"
                f".env 또는 GGUF_MODEL_PATH 환경 변수로 경로를 지정하세요."
            )
        logger.info(f"GGUF 모델 로딩 중: {model_path}")
        self.model = Llama(
            model_path=str(model_path),
            n_gpu_layers=settings.n_gpu_layers,
            n_ctx=settings.n_ctx,
            n_batch=settings.n_batch,
            verbose=False,
        )
        logger.info("모델 준비 완료 (CUDA GPU 전체 오프로드)")

    def warmup(self) -> None:
        """서버 시작 시 CUDA 커널 사전 컴파일용 더미 추론"""
        logger.info("모델 워밍업 시작...")
        try:
            list(self.stream_generate(
                messages=[{"role": "user", "content": "안녕"}],
                max_new_tokens=1,
            ))
            logger.info("모델 워밍업 완료")
        except Exception as e:
            logger.warning(f"워밍업 중 오류 (무시): {e}")

    def stream_generate(
        self,
        messages: list[dict],
        max_new_tokens: int = 2048,
        temperature: float = 0.85,
        top_p: float = 0.92,
        repetition_penalty: float = 1.1,
    ) -> Generator[str, None, None]:
        """토큰 단위 스트리밍 제너레이터"""

        response = self.model.create_chat_completion(
            messages=messages,
            max_tokens=max_new_tokens,
            temperature=temperature,
            top_p=top_p,
            repeat_penalty=repetition_penalty,
            stream=True,
        )
        for chunk in response:
            content = chunk["choices"][0]["delta"].get("content", "")
            if content:
                yield content
