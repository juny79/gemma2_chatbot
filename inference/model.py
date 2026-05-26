import os
import torch
from typing import Generator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# Windows에서 llama_cpp 임포트 전에 torch 번들 CUDA DLL 경로를 추가해야 함
_torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
os.add_dll_directory(_torch_lib)

from llama_cpp import Llama  # noqa: E402

# GGUF 모델 경로
GGUF_PATH = str(Path(__file__).parent.parent / "models" / "gemma-2-9b-it-Q4_K_M.gguf")


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
        logger.info(f"GGUF 모델 로딩 중: {GGUF_PATH}")
        self.model = Llama(
            model_path=GGUF_PATH,
            n_gpu_layers=-1,   # 전체 레이어를 GPU에 오프로드
            n_ctx=4096,        # 컨텍스트 윈도우
            n_batch=512,       # 배치 크기
            verbose=False,
        )
        logger.info("모델 준비 완료 (CUDA GPU 전체 오프로드)")

    def stream_generate(
        self,
        messages: list[dict],
        max_new_tokens: int = 512,
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
