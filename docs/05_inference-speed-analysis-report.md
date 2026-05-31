# 추론 속도 저하 원인 분석 및 개선 보고서

**프로젝트**: 점마 뭐꼬? — 웹소설/시나리오 창작 챗봇  
**작성일**: 2026-05-26  
**환경**: Windows 11, Python 3.11.0, NVIDIA GeForce RTX 3070 (8GB VRAM), CUDA 12.1

---

## 1. 문제 정의

Phase 1 구현 완료 후 실제 사용 시 응답 속도가 **3~8 tok/s** 수준으로 느리다는 문제가 발견되었다. 이는 창작 보조 챗봇으로서 사용성을 크게 저하시키는 수준이었다.

- **기대 속도**: RTX 3070 기준 20~40 tok/s
- **실제 속도**: 3~8 tok/s
- **체감**: 200토큰 응답 생성에 30~60초 소요

---

## 2. 원인 분석

### 2-1. AutoAWQ 아키텍처 개요

Phase 1에서는 `solidrust/gemma-2-9b-it-AWQ` 모델을 AutoAWQ 라이브러리로 로딩하여 사용하였다.

```
[모델] Gemma-2-9B AWQ (4-bit 양자화)
[라이브러리] AutoAWQ 0.2.7.post3
[커널] autoawq-kernels (CUDA 가속 연산자)
[프레임워크] PyTorch 2.5.1+cu121 + transformers
```

AWQ(Activation-aware Weight Quantization)의 실제 CUDA 가속은 `autoawq-kernels` 패키지에서 제공하는 커스텀 CUDA 연산자(`awq_ext`)가 담당한다. 이 커널이 정상 작동해야 **진짜 4-bit 행렬 곱셈 가속(GEMM)** 이 이루어진다.

### 2-2. 근본 원인: AWQ CUDA 커널 DLL 로딩 실패

`autoawq-kernels` 패키지의 `awq_ext` 모듈이 Windows 환경에서 로딩에 실패하였다.

#### 진단 결과

```
# autoawq-kernels 0.0.7
ImportError: DLL load failed while importing awq_ext:
지정된 프로시저를 찾을 수 없습니다.
→ DLL은 로딩됐으나, 심볼(함수) 탐색 실패 (GetProcAddress 오류)

# autoawq-kernels 0.0.9 (업그레이드 시도 후)
ImportError: DLL load failed while importing awq_ext:
지정된 모듈을 찾을 수 없습니다.
→ DLL 자체 로딩 실패 (LoadLibrary 오류, 의존 DLL 없음)
```

#### 오류의 의미

| 오류 유형 | 원인 | 비고 |
|---|---|---|
| `지정된 프로시저를 찾을 수 없습니다` | DLL 로딩 성공, 함수 심볼 없음 | CUDA 버전 불일치 가능성 |
| `지정된 모듈을 찾을 수 없습니다` | 의존 DLL(CUDA Runtime 등)을 찾지 못함 | PATH에 CUDA 런타임 없음 |

#### 핵심 원인

1. **CUDA Toolkit 미설치**: `cudart64_12.dll`, `cublas64_12.dll` 등 CUDA Runtime DLL이 시스템 PATH에 없었다. PyTorch는 자체 번들 DLL을 내부적으로 로딩하지만, 서드파티 CUDA 확장은 시스템 DLL에 의존한다.

2. **Windows 전용 사전 빌드 휠 부재**: `autoawq-kernels` 의 Windows + CUDA 조합 사전 빌드 휠이 현재 시스템(Python 3.11 + CUDA 12.1)에 맞지 않았다.

3. **버전 호환성 문제**: PyTorch가 번들링한 CUDA 버전과 `autoawq-kernels`가 빌드 타겟으로 한 CUDA 버전 사이의 ABI 불일치.

### 2-3. Fallback 경로: Naive Dequant

AWQ 커널이 실패하면 AutoAWQ는 자동으로 **naive dequantization** 경로로 폴백한다.

```
# 실제 경고 메시지 (추론 시 출력됨)
UserWarning: Skipping fusing modules because AWQ extension is not installed.
UserWarning: Using naive (slow) implementation.
```

**Naive Dequant 동작 방식**:
```
[4-bit 가중치] → [FP16/FP32 역양자화] → [일반 행렬 곱셈]
```

- 매 추론마다 4-bit → FP16 변환 수행 → **메모리 대역폭 낭비**
- PyTorch의 표준 `torch.mm` 사용 (AWQ 전용 커널 미사용)
- GPU는 사용되지만 **최적화된 연산자 없이 비효율적으로 동작**
- 결과: 본래 기대치(20~35 tok/s)의 **1/5~1/10 수준 속도**

### 2-4. 추가 시도: autoawq-kernels 0.0.9 업그레이드 실패

0.0.7에서의 문제 해결을 위해 0.0.9로 업그레이드를 시도하였으나, 설치 과정에서 **PyTorch가 CPU 전용 버전(2.12.0)으로 교체**되는 부작용이 발생하였다.

```
# 의도치 않은 결과
torch 2.5.1+cu121  →  torch 2.12.0  (CPU only)
CUDA: True         →  CUDA: False
```

즉시 `torch 2.5.1+cu121`로 복구하였으며, AWQ 커널 문제는 **Windows + CUDA 12.1 환경에서 구조적으로 해결 불가** 판정을 내렸다.

---

## 3. 해결 방법 선택

AWQ 커널 문제가 구조적 한계임을 확인한 후, 다음 4가지 대안을 검토하였다.

| 방법 | 예상 속도 | 작업 규모 | 위험도 | 비고 |
|---|---|---|---|---|
| **A. llama-cpp-python + GGUF** | ~20~35 tok/s | 중간 (모델 재다운로드) | 낮음 | Windows 안정적 |
| B. `torch.compile()` 적용 | ~10~20% 향상 | 최소 (코드 1줄) | 낮음 | 폴백 상태에서 효과 미미 |
| C. `max_new_tokens` 기본값 축소 | 체감 빠름 | 즉시 | 없음 | 품질 영향 최소 |
| D. Gemma-2-2B 모델 교체 | ~40~60 tok/s | 소 (모델 재다운로드) | 낮음 | 품질 하락 가능 |

**선택: 방법 A** — 가장 큰 실질적 속도 향상이 가능하고, llama.cpp는 Windows CUDA를 안정적으로 지원한다.

---

## 4. 변경 이력 (단계별)

### Step 1. llama-cpp-python 설치

**문제**: `abetlen.github.io` pip 인덱스의 cu121 휠은 **Linux 전용**으로만 제공.

**해결**: GitHub Releases에서 Windows + Python 3.11 + CUDA 12.1 전용 휠을 직접 설치.

```powershell
pip install "https://github.com/abetlen/llama-cpp-python/releases/download/v0.3.4-cu121/llama_cpp_python-0.3.4-cp311-cp311-win_amd64.whl"
```

**설치 결과**:
- `llama-cpp-python 0.3.4` + `diskcache 5.6.3` 설치 완료
- 휠 크기: 448.3 MB

---

### Step 2. Windows CUDA DLL 경로 문제 해결

**문제**: `llama.dll` 로딩 시 의존 DLL을 찾지 못하는 오류 발생.

```
RuntimeError: Failed to load shared library 'llama.dll':
Could not find module '...llama_cpp\lib\llama.dll' (or one of its dependencies).
```

**원인**: 시스템에 CUDA Toolkit이 설치되지 않아 `cudart64_12.dll`, `cublas64_12.dll` 등이 PATH에 없었다.

**발견**: PyTorch 번들 디렉터리 `venv/Lib/site-packages/torch/lib/`에 필요한 모든 CUDA DLL이 포함되어 있었다.

```
# torch/lib/ 내 CUDA DLL 목록
cudart64_12.dll
cublas64_12.dll
cublasLt64_12.dll
cufft64_11.dll
cusolver64_11.dll
cusparse64_12.dll
curand64_10.dll
cudnn64_9.dll  ... (외 다수)
```

**해결**: `os.add_dll_directory()`를 사용하여 Python 레벨에서 DLL 탐색 경로 추가.

```python
import os, torch
_torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
os.add_dll_directory(_torch_lib)  # llama_cpp import 전에 반드시 호출
from llama_cpp import Llama
```

**확인**:
```
ggml_cuda_init: found 1 CUDA devices:
  Device 0: NVIDIA GeForce RTX 3070, compute capability 8.6, VMM: yes
GPU offload support: True
```

---

### Step 3. Gemma-2-9B GGUF 모델 다운로드

**소스**: `bartowski/gemma-2-9b-it-GGUF` (HuggingFace)  
**파일**: `gemma-2-9b-it-Q4_K_M.gguf` (Q4_K_M 양자화)  
**크기**: 5.76 GB  
**저장 경로**: `models/gemma-2-9b-it-Q4_K_M.gguf`

```python
from huggingface_hub import hf_hub_download
hf_hub_download(
    repo_id='bartowski/gemma-2-9b-it-GGUF',
    filename='gemma-2-9b-it-Q4_K_M.gguf',
    local_dir='models',
)
```

**Q4_K_M 선택 이유**: 속도/품질/VRAM 균형이 가장 우수한 양자화 레벨.

| 양자화 | 파일 크기 | 품질 손실 | 속도 |
|---|---|---|---|
| Q2_K | ~3.2GB | 높음 | 매우 빠름 |
| Q4_K_M | ~5.8GB | 낮음 | 빠름 ✅ |
| Q6_K | ~7.2GB | 매우 낮음 | 보통 |
| Q8_0 | ~9.4GB | 거의 없음 | 느림 (VRAM 초과) |

---

### Step 4. inference/model.py 교체

#### 이전 코드 (AutoAWQ 기반)

```python
import torch
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer, TextIteratorStreamer
from threading import Thread

MODEL_PATH = ".../models/gemma-2-9b-it-AWQ"

class GemmaInference:
    def _load(self):
        self.tokenizer = AutoTokenizer.from_pretrained(MODEL_PATH)
        self.model = AutoAWQForCausalLM.from_quantized(
            MODEL_PATH, fuse_layers=True, safetensors=True
        )

    def stream_generate(self, messages, ...):
        text = self.tokenizer.apply_chat_template(messages, ...)
        inputs = self.tokenizer([text], return_tensors="pt").to("cuda")
        streamer = TextIteratorStreamer(self.tokenizer, ...)
        thread = Thread(target=self.model.generate, kwargs={...})
        thread.start()
        for token in streamer:
            yield token
        thread.join()
```

#### 현재 코드 (llama-cpp-python 기반)

```python
import os, torch
from llama_cpp import Llama

# Windows CUDA DLL 경로 해결
_torch_lib = os.path.join(os.path.dirname(torch.__file__), "lib")
os.add_dll_directory(_torch_lib)

GGUF_PATH = ".../models/gemma-2-9b-it-Q4_K_M.gguf"

class GemmaInference:
    def _load(self):
        self.model = Llama(
            model_path=GGUF_PATH,
            n_gpu_layers=-1,  # 전체 GPU 오프로드
            n_ctx=4096,
            n_batch=512,
            verbose=False,
        )

    def stream_generate(self, messages, ...):
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
```

**주요 변경점**:
- 토크나이저 별도 로딩 → llama.cpp 내장 토크나이저로 통합
- `Thread` + `TextIteratorStreamer` 패턴 → `create_chat_completion(stream=True)` 직접 사용
- 채팅 템플릿 처리 → GGUF 메타데이터의 템플릿을 llama.cpp가 자동 적용
- AWQ/transformers 의존성 제거 (llama_cpp만으로 완결)

> `main.py`, `schemas.py`, `prompts.py`, `database.py`, `frontend/index.html` 은 **변경 없음** — `stream_generate()` 인터페이스가 동일하게 유지됨.

---

## 5. 이전 vs 현재 비교 분석

### 5-1. 구성 비교

| 항목 | 이전 (AutoAWQ) | 현재 (llama-cpp-python) |
|---|---|---|
| **모델 파일** | `gemma-2-9b-it-AWQ/` (AWQ safetensors, ~8GB) | `gemma-2-9b-it-Q4_K_M.gguf` (단일 파일, ~5.8GB) |
| **추론 라이브러리** | AutoAWQ 0.2.7.post3 + transformers | llama-cpp-python 0.3.4 |
| **CUDA 가속 방식** | autoawq-kernels (커스텀 CUDA 커널) | ggml-cuda.dll (llama.cpp 내장 CUDA) |
| **토크나이저** | HuggingFace tokenizers (별도 로딩) | GGUF 내장 토크나이저 |
| **채팅 템플릿** | `apply_chat_template()` 수동 적용 | GGUF 메타데이터 자동 적용 |
| **스트리밍 구현** | Thread + TextIteratorStreamer | `stream=True` 네이티브 지원 |
| **Windows CUDA** | ❌ awq_ext DLL 로딩 실패 | ✅ torch/lib DLL 경로 주입으로 해결 |

### 5-2. 성능 비교

| 지표 | 이전 | 현재 | 변화 |
|---|---|---|---|
| **생성 속도** | 3~8 tok/s | **~22 tok/s** | **+5~7배** |
| **200토큰 응답 소요** | 25~65초 | **~9초** | **약 1/6 단축** |
| **서버 시작(모델 로딩)** | ~20초 | **~3초** | **약 1/7 단축** |
| **VRAM 사용량** | ~7.5GB (FP16 dequant 포함) | **~5.5GB** | -2GB 절감 |
| **GPU 활용** | 비효율 (naive fallback) | **완전 GPU 오프로드** | 정상화 |

### 5-3. 실측 데이터

```
테스트 프롬프트: "판타지 웹소설에 등장하는 주인공을 소개해줘. 200자 정도로."
max_new_tokens: 200

[결과]
생성 토큰 수: 166
소요 시간: 7.6초
속도: 21.8 tok/s
```

### 5-4. 기술 스택 변화

```
[이전]
Python 3.11
├── PyTorch 2.5.1+cu121
├── AutoAWQ 0.2.7.post3
│   └── autoawq-kernels 0.0.7  ← DLL 실패로 비활성화
├── transformers 4.x
│   └── TextIteratorStreamer
└── FastAPI + uvicorn

[현재]
Python 3.11
├── PyTorch 2.5.1+cu121  (CUDA DLL 소스로 활용)
├── llama-cpp-python 0.3.4
│   └── ggml-cuda.dll  ← GPU 연산 정상 작동
└── FastAPI + uvicorn
```

---

## 6. 남은 제약 및 개선 가능성

### 현재 제약

| 항목 | 내용 |
|---|---|
| 컨텍스트 길이 | 4096 토큰 (모델 학습 기준 8192의 절반) |
| 단일 요청 처리 | llama-cpp 단일 스레드 처리 방식 |
| 모델 고정 | 서버 재시작 없이 모델 교체 불가 |

### 추가 개선 가능 방안

1. **컨텍스트 확장**: `n_ctx=8192`로 설정 시 더 긴 대화 컨텍스트 지원 (VRAM +1.5GB 추가 필요)
2. **Flash Attention 활성화**: RTX 3070 (Ampere, compute 8.6) 지원 — `n_gpu_layers=-1` 상태에서 추가 속도 향상 가능
3. **Phase 2 RAG 연동**: LangChain + ChromaDB 기반 RAG는 기존 설계 그대로 적용 가능 (model.py 교체에 영향 없음)

---

## 7. 결론

AutoAWQ의 CUDA 가속 커널(`awq_ext`)이 Windows 환경에서 CUDA Toolkit 미설치로 인한 DLL 의존성 문제로 완전히 비활성화되어, 4-bit AWQ 모델이 역양자화 폴백 경로로만 동작하고 있었다. 이것이 3~8 tok/s 저속의 근본 원인이었다.

llama-cpp-python + GGUF 전환을 통해 동일한 RTX 3070에서 **~22 tok/s** 를 달성하였으며, 이는 웹소설 창작 보조 챗봇으로 실사용이 가능한 수준이다. 또한 서버 API 인터페이스는 일체 변경되지 않아 프런트엔드 및 세션 관리 시스템은 그대로 유지된다.
