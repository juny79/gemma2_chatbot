# ── 베이스 이미지 (CUDA 12.1 + Python 3.11) ───────────────────────────────────
FROM nvidia/cuda:12.1.1-cudnn8-devel-ubuntu22.04

ENV DEBIAN_FRONTEND=noninteractive \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1

# ── 시스템 패키지 ──────────────────────────────────────────────────────────────
RUN apt-get update && apt-get install -y --no-install-recommends \
    python3.11 python3.11-venv python3-pip \
    build-essential cmake \
    && rm -rf /var/lib/apt/lists/*

RUN update-alternatives --install /usr/bin/python3 python3 /usr/bin/python3.11 1 \
    && update-alternatives --install /usr/bin/python python /usr/bin/python3.11 1

WORKDIR /app

# ── Python 의존성 설치 ─────────────────────────────────────────────────────────
# llama-cpp-python은 CUDA 빌드 플래그가 필요하므로 별도 설치
COPY requirements.txt .

RUN pip install --upgrade pip && \
    pip install torch==2.5.1+cu121 --index-url https://download.pytorch.org/whl/cu121 && \
    CMAKE_ARGS="-DGGML_CUDA=on" pip install llama-cpp-python==0.3.4 --no-cache-dir && \
    pip install -r requirements.txt

# ── 소스 복사 ─────────────────────────────────────────────────────────────────
COPY inference/ ./inference/
COPY frontend/ ./frontend/
COPY .env* ./

# ── 모델 디렉토리 (볼륨으로 마운트 권장) ──────────────────────────────────────
VOLUME ["/app/models", "/app/data"]

EXPOSE 8000

# 기본 실행: inference/main.py
CMD ["python", "inference/main.py"]
