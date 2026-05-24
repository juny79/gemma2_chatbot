import torch
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer, TextIteratorStreamer
from threading import Thread
from typing import Generator
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

# inference/ 폴더 기준으로 상위 디렉토리의 models 폴더를 절대 경로로 지정
MODEL_PATH = str(Path(__file__).parent.parent / "models" / "gemma-2-9b-it-AWQ")


class GemmaInference:
    """AutoAWQ 기반 Gemma-2 추론 싱글턴 클래스"""

    _instance: "GemmaInference | None" = None

    def __init__(self):
        self.model = None
        self.tokenizer = None
        self._load()

    @classmethod
    def get_instance(cls) -> "GemmaInference":
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def _load(self):
        logger.info("토크나이저 로딩 중...")
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)

        logger.info("모델 로딩 중 (VRAM에 AWQ 가중치 적재)...")
        self.model = AutoAWQForCausalLM.from_quantized(
            MODEL_PATH,
            fuse_layers=True,
            safetensors=True,
        )
        device = next(self.model.parameters()).device
        logger.info(f"모델 준비 완료: {device}")

    def stream_generate(
        self,
        messages: list[dict],
        max_new_tokens: int = 512,
        temperature: float = 0.85,
        top_p: float = 0.92,
        repetition_penalty: float = 1.1,
    ) -> Generator[str, None, None]:
        """토큰 단위 스트리밍 제너레이터"""

        # 채팅 템플릿 적용
        text = self.tokenizer.apply_chat_template(
            messages,
            tokenize=False,
            add_generation_prompt=True,
        )
        inputs = self.tokenizer([text], return_tensors="pt").to("cuda")

        streamer = TextIteratorStreamer(
            self.tokenizer,
            skip_prompt=True,
            skip_special_tokens=True,
        )

        generation_kwargs = {
            **inputs,
            "streamer": streamer,
            "max_new_tokens": max_new_tokens,
            "temperature": temperature,
            "top_p": top_p,
            "repetition_penalty": repetition_penalty,
            "do_sample": True,
        }

        # 별도 스레드에서 generation 실행
        thread = Thread(target=self.model.generate, kwargs=generation_kwargs, daemon=True)
        thread.start()

        for token in streamer:
            yield token

        thread.join()
