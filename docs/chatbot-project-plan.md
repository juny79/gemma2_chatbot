# Gemma-2-9b-it-AWQ 기반 챗봇 서비스 상세 계획서

> **모델**: `solidrust/gemma-2-9b-it-AWQ` (HuggingFace)  
> **로컬 GPU**: NVIDIA RTX 3070 8GB VRAM  
> **작성일**: 2026-05-12

---

## 목차

1. [프로젝트 개요](#1-프로젝트-개요)
2. [하드웨어 및 환경 분석](#2-하드웨어-및-환경-분석)
3. [전체 시스템 아키텍처](#3-전체-시스템-아키텍처)
4. [기술 스택 상세](#4-기술-스택-상세)
5. [단계별 구현 계획](#5-단계별-구현-계획)
6. [CI/CD 파이프라인 설계](#6-cicd-파이프라인-설계)
7. [코드 리뷰 에이전트 설계](#7-코드-리뷰-에이전트-설계)
8. [웹 & 앱 서비스 배포 전략](#8-웹--앱-서비스-배포-전략)
9. [모니터링 및 운영](#9-모니터링-및-운영)
10. [디렉토리 구조](#10-디렉토리-구조)
11. [리스크 및 대응 방안](#11-리스크-및-대응-방안)

---

## 1. 프로젝트 개요

### 1.1 목표

`solidrust/gemma-2-9b-it-AWQ` 모델을 로컬 RTX 3070 GPU에서 실행하여, 실사용 가능한 챗봇 웹/앱 서비스를 구축하고, GitHub 기반 CI/CD 파이프라인과 AI 코드 리뷰 에이전트를 통해 실무 수준의 개발 이력을 관리한다.

### 1.2 핵심 요구사항

| 구분 | 요구사항 |
|------|----------|
| AI 모델 | `solidrust/gemma-2-9b-it-AWQ` (4-bit AWQ 양자화, HuggingFace) |
| 추론 환경 | 로컬 RTX 3070 8GB, AutoAWQ 기반 추론 |
| 웹 서비스 | Next.js 기반 챗봇 웹 UI (반응형) |
| 앱 서비스 | Flutter 기반 iOS/Android 앱 |
| 외부 노출 | Cloudflare Tunnel (고정 IP 불필요) |
| 배포 자동화 | GitHub Actions + Self-hosted Runner |
| 코드 품질 | Gemma-2 기반 PR 코드 리뷰 에이전트 |
| 개발 이력 | GitHub PR/Issue를 통한 모든 변경사항 추적 |

### 1.3 AWQ 모델 선택 이유

일반 Gemma-2-9b-it 모델은 FP16 기준 약 18GB VRAM이 필요하여 RTX 3070 8GB에서 실행 불가하다.  
`solidrust/gemma-2-9b-it-AWQ`는 4-bit AWQ(Activation-aware Weight Quantization) 양자화 모델로, **약 5~6GB VRAM**에서 실행 가능하며 성능 저하가 최소화된다.

---

## 2. 하드웨어 및 환경 분석

### 2.1 로컬 환경 스펙 (추정/기준)

| 항목 | 사양 |
|------|------|
| GPU | NVIDIA RTX 3070 (8GB GDDR6) |
| CUDA | CUDA 11.8 이상 권장 (12.x 최적) |
| OS | Windows 10/11 or Ubuntu 22.04 |
| RAM | 16GB 이상 권장 |
| 저장공간 | 모델 다운로드용 SSD 20GB 이상 여유 |

### 2.2 VRAM 사용량 추정

| 구성 요소 | 예상 VRAM |
|-----------|-----------|
| solidrust/gemma-2-9b-it-AWQ (4-bit) | ~5.5 GB |
| KV Cache (추론 중 컨텍스트 4096 tokens) | ~0.8 GB |
| Python 런타임 오버헤드 | ~0.3 GB |
| **합계** | **~6.6 GB** ← RTX 3070 8GB 내 수용 가능 |

> ⚠️ **주의**: 동시 요청이 많아지면 배치 처리 시 VRAM 초과 가능. max_new_tokens, 배치 크기 제한 필수.

### 2.3 추론 프레임워크 비교 및 선택

| 프레임워크 | AWQ 지원 | RTX 3070 호환 | 비고 |
|------------|----------|----------------|------|
| **AutoAWQ + Transformers** | ✅ 네이티브 | ✅ | 권장 (직접 HuggingFace 로드) |
| vLLM | ✅ | ✅ (Linux 필요) | 고성능, Windows 불안정 |
| Text-Generation-Inference | ✅ | ✅ (Docker) | HuggingFace 공식, Docker 필요 |
| Ollama | ❌ GGUF만 지원 | ✅ | AWQ 모델 직접 지원 불가 |

> **최종 선택**: **AutoAWQ + Transformers** (Windows/Linux 모두 지원, HuggingFace 직접 연동)  
> 또는 고성능 필요시 **TGI (Text-Generation-Inference) via Docker**

---

## 3. 전체 시스템 아키텍처

```
┌─────────────────────────────────────────────────────────────────┐
│                        로컬 PC (RTX 3070)                        │
│                                                                   │
│  ┌──────────────────┐    ┌─────────────────────────────────────┐ │
│  │  AI 추론 서버     │    │           백엔드 API 서버             │ │
│  │                  │    │                                     │ │
│  │  AutoAWQ         │◄───│  FastAPI (Python)                   │ │
│  │  + Transformers  │    │  - /chat (스트리밍)                  │ │
│  │                  │    │  - /history                         │ │
│  │  gemma-2-9b-it   │    │  - /auth                            │ │
│  │  -AWQ            │    │  - WebSocket                        │ │
│  │  (Port: 8001)    │    │  (Port: 8000)                       │ │
│  └──────────────────┘    └──────────────┬──────────────────────┘ │
│                                         │                         │
│  ┌──────────────────┐    ┌──────────────▼──────────────────────┐ │
│  │  벡터 DB         │    │           데이터베이스               │ │
│  │  ChromaDB        │◄───│  PostgreSQL                         │ │
│  │  (RAG 지원)      │    │  - 사용자 정보                       │ │
│  │  (Port: 8002)    │    │  - 채팅 히스토리                     │ │
│  └──────────────────┘    │  (Port: 5432)                       │ │
│                           └─────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │              프론트엔드 (Next.js)  Port: 3000                 │ │
│  └──────────────────────────────────────────────────────────────┘ │
│                                                                   │
│  ┌──────────────────────────────────────────────────────────────┐ │
│  │         GitHub Actions Self-hosted Runner (백그라운드)        │ │
│  └──────────────────────────────────────────────────────────────┘ │
└─────────────────────────┬───────────────────────────────────────┘
                          │
              Cloudflare Tunnel (HTTPS)
                          │
          ┌───────────────┴───────────────┐
          │                               │
   ┌──────▼──────┐                ┌───────▼──────┐
   │  웹 브라우저  │                │  Flutter 앱   │
   │ (Next.js UI) │                │ (iOS/Android) │
   └─────────────┘                └──────────────┘
                          │
               ┌──────────▼──────────┐
               │     GitHub          │
               │  - PR/Issues        │
               │  - Actions CI/CD    │
               │  - Code Review Bot  │
               └─────────────────────┘
```

---

## 4. 기술 스택 상세

### 4.1 AI 추론 계층

| 항목 | 기술 | 버전 | 용도 |
|------|------|------|------|
| 모델 | solidrust/gemma-2-9b-it-AWQ | latest | 대화 생성 |
| 추론 라이브러리 | AutoAWQ | ≥0.2.5 | AWQ 양자화 추론 |
| 딥러닝 프레임워크 | PyTorch | ≥2.1 (CUDA 12.x) | GPU 연산 |
| 모델 로딩 | transformers | ≥4.40 | HuggingFace 모델 관리 |
| 스트리밍 | TextIteratorStreamer | - | 실시간 토큰 스트리밍 |

### 4.2 백엔드 API 계층

| 항목 | 기술 | 버전 | 용도 |
|------|------|------|------|
| 웹 프레임워크 | FastAPI | ≥0.110 | REST API + WebSocket |
| ASGI 서버 | Uvicorn | ≥0.29 | 비동기 서버 실행 |
| ORM | SQLAlchemy | ≥2.0 | PostgreSQL 연동 |
| 인증 | python-jose + passlib | - | JWT 인증 |
| 유효성 검사 | Pydantic | v2 | 요청/응답 모델 |
| HTTP 클라이언트 | httpx | - | 내부 서비스 통신 |

### 4.3 데이터 계층

| 항목 | 기술 | 용도 |
|------|------|------|
| 관계형 DB | PostgreSQL 15 | 사용자, 채팅 히스토리 |
| 벡터 DB | ChromaDB | RAG 지식 베이스 |
| 임베딩 | sentence-transformers | 텍스트 벡터화 |
| 캐시 | Redis | 세션, 응답 캐시 |

### 4.4 프론트엔드 (Web)

| 항목 | 기술 | 버전 | 용도 |
|------|------|------|------|
| 프레임워크 | Next.js (App Router) | ≥14 | 웹 UI |
| 언어 | TypeScript | ≥5 | 타입 안전성 |
| 상태관리 | Zustand | - | 글로벌 상태 |
| UI 컴포넌트 | shadcn/ui + Tailwind CSS | - | 챗봇 UI |
| 스트리밍 렌더링 | EventSource (SSE) | - | 실시간 토큰 출력 |
| 마크다운 렌더링 | react-markdown | - | AI 응답 포맷팅 |

### 4.5 모바일 앱 (Flutter)

| 항목 | 기술 | 용도 |
|------|------|------|
| 프레임워크 | Flutter 3.x | Android/iOS 크로스플랫폼 |
| 언어 | Dart | 앱 로직 |
| HTTP 통신 | dio | API 호출 |
| 상태관리 | Riverpod | 앱 상태 |
| 로컬 저장소 | flutter_secure_storage | 토큰 저장 |

### 4.6 인프라 및 DevOps

| 항목 | 기술 | 용도 |
|------|------|------|
| 외부 터널링 | Cloudflare Tunnel (cloudflared) | 로컬→HTTPS 노출 |
| 컨테이너화 | Docker + Docker Compose | 서비스 격리 |
| CI/CD | GitHub Actions + Self-hosted Runner | 자동 빌드/배포 |
| 에이전트 프레임워크 | LangChain | 코드 리뷰 에이전트 |
| 모니터링 | Prometheus + Grafana | GPU/API 지표 수집 |
| 로그 수집 | Loki + Promtail | 중앙 로그 관리 |

---

## 5. 단계별 구현 계획

### Phase 1: 로컬 AI 추론 서버 구축 (1~2주)

**목표**: RTX 3070에서 AWQ 모델이 안정적으로 동작하는 추론 서버 완성

#### Step 1-1: 환경 설정

```bash
# Python 가상환경 생성
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 핵심 패키지 설치
pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
pip install autoawq transformers accelerate
pip install fastapi uvicorn[standard] pydantic
```

#### Step 1-2: 모델 다운로드 및 로드 테스트

```python
# model_loader.py
from awq import AutoAWQForCausalLM
from transformers import AutoTokenizer

MODEL_ID = "solidrust/gemma-2-9b-it-AWQ"

def load_model():
    tokenizer = AutoTokenizer.from_pretrained(MODEL_ID)
    model = AutoAWQForCausalLM.from_pretrained(
        MODEL_ID,
        device_map="cuda",
        torch_dtype="auto",
        low_cpu_mem_usage=True
    )
    return model, tokenizer
```

#### Step 1-3: FastAPI 추론 서버 구현

```python
# inference_server.py
from fastapi import FastAPI
from fastapi.responses import StreamingResponse
from transformers import TextIteratorStreamer
from threading import Thread
import torch

app = FastAPI()

@app.post("/generate")
async def generate(request: ChatRequest):
    inputs = tokenizer(request.prompt, return_tensors="pt").to("cuda")
    streamer = TextIteratorStreamer(tokenizer, skip_prompt=True)
    
    generation_kwargs = {
        **inputs,
        "streamer": streamer,
        "max_new_tokens": 512,
        "temperature": 0.7,
        "do_sample": True,
    }
    
    thread = Thread(target=model.generate, kwargs=generation_kwargs)
    thread.start()
    
    def stream_generator():
        for token in streamer:
            yield f"data: {token}\n\n"
    
    return StreamingResponse(stream_generator(), media_type="text/event-stream")
```

#### Step 1-4: 컨텍스트 및 시스템 프롬프트 설계

```python
SYSTEM_PROMPT = """당신은 친절하고 전문적인 AI 어시스턴트입니다. 
사용자의 질문에 정확하고 도움이 되는 답변을 제공하세요.
답변은 한국어로 작성하되, 기술적 내용은 영어 용어를 적절히 활용하세요."""

def build_prompt(history: list[dict], user_message: str) -> str:
    messages = [{"role": "system", "content": SYSTEM_PROMPT}]
    messages.extend(history)
    messages.append({"role": "user", "content": user_message})
    return tokenizer.apply_chat_template(
        messages, tokenize=False, add_generation_prompt=True
    )
```

---

### Phase 2: 백엔드 API 서버 구축 (2~3주)

**목표**: 인증, 히스토리 관리, RAG를 포함한 완전한 백엔드 완성

#### Step 2-1: 데이터베이스 스키마 설계

```sql
-- users 테이블
CREATE TABLE users (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(255) UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);

-- conversations 테이블
CREATE TABLE conversations (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id UUID REFERENCES users(id) ON DELETE CASCADE,
    title VARCHAR(255),
    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- messages 테이블
CREATE TABLE messages (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    conversation_id UUID REFERENCES conversations(id) ON DELETE CASCADE,
    role VARCHAR(20) NOT NULL,  -- 'user' | 'assistant'
    content TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT NOW()
);
```

#### Step 2-2: API 엔드포인트 구조

```
POST   /api/auth/register          # 회원가입
POST   /api/auth/login             # 로그인 (JWT 발급)
POST   /api/auth/refresh           # 토큰 갱신

GET    /api/conversations          # 대화 목록
POST   /api/conversations          # 새 대화 시작
DELETE /api/conversations/{id}     # 대화 삭제

POST   /api/chat                   # 메시지 전송 (SSE 스트리밍)
GET    /api/chat/{conversation_id} # 대화 히스토리 조회

POST   /api/rag/upload             # 문서 업로드 (RAG)
GET    /api/rag/search             # 벡터 검색
```

#### Step 2-3: Docker Compose 구성

```yaml
# docker-compose.yml
version: '3.8'
services:
  backend:
    build: ./backend
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - chromadb
      - redis
    environment:
      - DATABASE_URL=postgresql://user:password@postgres:5432/chatbot
      - REDIS_URL=redis://redis:6379
      - INFERENCE_SERVER_URL=http://host.docker.internal:8001
    volumes:
      - ./backend:/app

  postgres:
    image: postgres:15
    environment:
      POSTGRES_DB: chatbot
      POSTGRES_USER: user
      POSTGRES_PASSWORD: ${POSTGRES_PASSWORD}
    volumes:
      - postgres_data:/var/lib/postgresql/data
    ports:
      - "5432:5432"

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8002:8000"
    volumes:
      - chroma_data:/chroma/chroma

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"

volumes:
  postgres_data:
  chroma_data:
```

---

### Phase 3: 웹 프론트엔드 구현 (2주)

**목표**: 스트리밍 채팅 UI가 있는 Next.js 웹 앱 완성

#### Step 3-1: 프로젝트 초기화

```bash
npx create-next-app@latest frontend --typescript --tailwind --app
cd frontend
npx shadcn-ui@latest init
npx shadcn-ui@latest add button input textarea scroll-area
```

#### Step 3-2: 핵심 컴포넌트 구조

```
frontend/
├── app/
│   ├── (auth)/
│   │   ├── login/page.tsx
│   │   └── register/page.tsx
│   ├── chat/
│   │   ├── [conversationId]/page.tsx
│   │   └── page.tsx
│   └── layout.tsx
├── components/
│   ├── chat/
│   │   ├── ChatWindow.tsx       # 메시지 표시 영역
│   │   ├── MessageBubble.tsx    # 개별 메시지 버블
│   │   ├── ChatInput.tsx        # 입력창 + 전송 버튼
│   │   └── StreamingMessage.tsx # 스트리밍 중 메시지
│   └── sidebar/
│       └── ConversationList.tsx # 대화 목록 사이드바
└── lib/
    ├── api.ts                   # API 호출 함수
    └── streaming.ts             # SSE 스트리밍 처리
```

#### Step 3-3: SSE 스트리밍 구현

```typescript
// lib/streaming.ts
export async function streamChat(
  message: string,
  conversationId: string,
  onToken: (token: string) => void,
  onDone: () => void
) {
  const response = await fetch('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 
               'Authorization': `Bearer ${getToken()}` },
    body: JSON.stringify({ message, conversation_id: conversationId }),
  });

  const reader = response.body!.getReader();
  const decoder = new TextDecoder();

  while (true) {
    const { done, value } = await reader.read();
    if (done) { onDone(); break; }
    
    const chunk = decoder.decode(value);
    const lines = chunk.split('\n');
    for (const line of lines) {
      if (line.startsWith('data: ')) {
        onToken(line.slice(6));
      }
    }
  }
}
```

---

### Phase 4: Flutter 모바일 앱 구현 (2~3주)

**목표**: 웹과 동일한 기능을 제공하는 iOS/Android 앱 완성

#### Step 4-1: 프로젝트 초기화

```bash
flutter create mobile --org com.yourname.chatbot
cd mobile
flutter pub add dio riverpod flutter_riverpod
flutter pub add flutter_secure_storage
flutter pub add flutter_markdown
```

#### Step 4-2: 앱 화면 구조

```
mobile/lib/
├── main.dart
├── core/
│   ├── api/
│   │   ├── api_client.dart          # Dio HTTP 클라이언트
│   │   └── endpoints.dart           # API 엔드포인트 상수
│   └── providers/
│       ├── auth_provider.dart       # 인증 상태 관리
│       └── chat_provider.dart       # 채팅 상태 관리
├── features/
│   ├── auth/
│   │   ├── login_screen.dart
│   │   └── register_screen.dart
│   └── chat/
│       ├── chat_screen.dart         # 메인 채팅 화면
│       ├── conversation_list.dart   # 대화 목록
│       └── widgets/
│           ├── message_bubble.dart
│           └── chat_input.dart
└── shared/
    └── theme/
        └── app_theme.dart
```

---

### Phase 5: 외부 노출 및 배포 설정 (1주)

**목표**: Cloudflare Tunnel로 외부에서 안전하게 접근 가능한 서비스 완성

#### Step 5-1: Cloudflare Tunnel 설정

```bash
# cloudflared 설치 (Windows)
winget install Cloudflare.cloudflared

# 인증
cloudflared tunnel login

# 터널 생성
cloudflared tunnel create gemma-chatbot

# 터널 설정 파일
# ~/.cloudflared/config.yml
tunnel: <TUNNEL_ID>
credentials-file: ~/.cloudflared/<TUNNEL_ID>.json

ingress:
  - hostname: chat.yourdomain.com
    service: http://localhost:3000    # Next.js 웹
  - hostname: api.yourdomain.com
    service: http://localhost:8000    # FastAPI 백엔드
  - rule: "*"
    service: http_status:404

# 터널 실행
cloudflared tunnel run gemma-chatbot
```

#### Step 5-2: HTTPS 및 보안 설정

- Cloudflare SSL/TLS 모드: Full (Strict)
- WAF 규칙: SQL Injection, XSS 방어 활성화
- Rate Limiting: API 엔드포인트당 분당 60 요청 제한
- 환경변수: `.env` 파일로 분리, `.gitignore`에 추가

---

## 6. CI/CD 파이프라인 설계

### 6.1 GitHub Actions Self-hosted Runner 등록

```bash
# 로컬 PC에서 GitHub Runner 설치 (Windows PowerShell)
mkdir actions-runner; cd actions-runner
# GitHub > Repository > Settings > Actions > Runners > New self-hosted runner
# 안내에 따라 runner 설치 및 등록

# 서비스로 등록 (Windows)
.\svc.ps1 install
.\svc.ps1 start
```

### 6.2 자동 배포 워크플로우

```yaml
# .github/workflows/deploy.yml
name: Deploy to Local Server

on:
  push:
    branches: [main]

jobs:
  deploy:
    runs-on: self-hosted
    steps:
      - name: Checkout
        uses: actions/checkout@v4

      - name: Pull latest changes
        run: git pull origin main

      - name: Rebuild backend
        run: |
          cd backend
          pip install -r requirements.txt
          
      - name: Rebuild frontend
        run: |
          cd frontend
          npm ci
          npm run build

      - name: Restart services
        run: |
          docker compose restart backend
          docker compose restart frontend

      - name: Health check
        run: |
          sleep 10
          curl -f http://localhost:8000/health || exit 1
          curl -f http://localhost:3000 || exit 1

      - name: Notify success
        if: success()
        run: echo "Deployment successful at $(date)"
```

### 6.3 테스트 자동화 워크플로우

```yaml
# .github/workflows/test.yml
name: Run Tests

on:
  pull_request:
    branches: [main, develop]

jobs:
  test-backend:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Run pytest
        run: |
          cd backend
          pip install -r requirements-dev.txt
          pytest tests/ -v --cov=app --cov-report=xml

  test-frontend:
    runs-on: self-hosted
    steps:
      - uses: actions/checkout@v4
      - name: Run Jest
        run: |
          cd frontend
          npm ci
          npm test -- --coverage
```

---

## 7. 코드 리뷰 에이전트 설계

### 7.1 에이전트 작동 원리

```
PR 생성/업데이트
       │
       ▼
GitHub Actions 트리거
       │
       ▼
git diff 추출 (변경된 파일/코드)
       │
       ▼
LangChain Agent 실행
       │
       ├─ 코딩 컨벤션 체크
       ├─ 잠재적 버그 탐지
       ├─ 보안 취약점 분석 (OWASP Top 10)
       ├─ 성능 이슈 감지
       └─ 개선 제안 생성
       │
       ▼
GitHub PR에 리뷰 댓글 자동 게시
```

### 7.2 코드 리뷰 에이전트 구현

```python
# agents/code_review_agent.py
import os
import subprocess
from langchain.llms.base import LLM
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain
import requests

class LocalGemmaLLM(LLM):
    """로컬 FastAPI 추론 서버를 LangChain LLM으로 래핑"""
    
    inference_url: str = "http://localhost:8001/generate"
    
    def _call(self, prompt: str, stop=None) -> str:
        response = requests.post(
            self.inference_url,
            json={"prompt": prompt, "max_new_tokens": 1024},
            timeout=120
        )
        return response.json()["generated_text"]
    
    @property
    def _llm_type(self) -> str:
        return "local_gemma"


REVIEW_PROMPT = PromptTemplate(
    input_variables=["diff", "file_path"],
    template="""당신은 전문 코드 리뷰어입니다. 다음 코드 변경사항을 분석하세요.

파일: {file_path}
변경사항 (git diff):
{diff}

다음 항목을 분석하고 한국어로 리뷰해주세요:
1. **버그 가능성**: 논리 오류, 엣지 케이스 처리 미흡
2. **보안 취약점**: SQL 인젝션, XSS, 민감정보 노출 등
3. **성능 문제**: 비효율적인 알고리즘, 불필요한 DB 쿼리
4. **코드 품질**: 가독성, 함수 분리, 명명 규칙
5. **개선 제안**: 구체적인 수정 방법 제시

리뷰 형식: 각 항목별로 ✅ (문제없음) 또는 ⚠️ (주의) 또는 ❌ (수정필요)로 표시
"""
)


def get_pr_diff(pr_number: str, repo: str) -> dict:
    """GitHub API로 PR diff 가져오기"""
    token = os.environ["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}", "Accept": "application/vnd.github.v3.diff"}
    url = f"https://api.github.com/repos/{repo}/pulls/{pr_number}/files"
    response = requests.get(url, headers=headers)
    return response.json()


def post_review_comment(pr_number: str, repo: str, body: str):
    """PR에 리뷰 댓글 게시"""
    token = os.environ["GITHUB_TOKEN"]
    headers = {"Authorization": f"token {token}"}
    url = f"https://api.github.com/repos/{repo}/issues/{pr_number}/comments"
    requests.post(url, headers=headers, json={"body": body})


def run_code_review(pr_number: str, repo: str):
    llm = LocalGemmaLLM()
    chain = LLMChain(llm=llm, prompt=REVIEW_PROMPT)
    
    files = get_pr_diff(pr_number, repo)
    reviews = []
    
    for file in files:
        if file.get("patch"):
            review = chain.run(
                diff=file["patch"][:3000],  # VRAM 절약을 위해 3000자 제한
                file_path=file["filename"]
            )
            reviews.append(f"## `{file['filename']}`\n\n{review}")
    
    full_review = "# 🤖 Gemma-2 코드 리뷰 결과\n\n" + "\n\n---\n\n".join(reviews)
    post_review_comment(pr_number, repo, full_review)
```

### 7.3 코드 리뷰 에이전트 GitHub Actions 워크플로우

```yaml
# .github/workflows/code-review.yml
name: AI Code Review

on:
  pull_request:
    types: [opened, synchronize]

jobs:
  ai-review:
    runs-on: self-hosted
    permissions:
      pull-requests: write
      contents: read
    steps:
      - uses: actions/checkout@v4
        with:
          fetch-depth: 0

      - name: Run AI Code Review
        env:
          GITHUB_TOKEN: ${{ secrets.GITHUB_TOKEN }}
          PR_NUMBER: ${{ github.event.pull_request.number }}
          REPO: ${{ github.repository }}
        run: |
          cd agents
          pip install -r requirements.txt
          python code_review_agent.py --pr $PR_NUMBER --repo $REPO
```

---

## 8. 웹 & 앱 서비스 배포 전략

### 8.1 환경 분리

| 환경 | 용도 | 브랜치 | URL |
|------|------|--------|-----|
| Development | 개발 중 테스트 | `develop` | `http://localhost:3000` |
| Staging | PR 머지 전 검증 | `staging` | `https://staging.yourdomain.com` |
| Production | 실서비스 | `main` | `https://chat.yourdomain.com` |

### 8.2 Flutter 앱 배포 전략

**Android**: GitHub Actions에서 APK 빌드 → GitHub Releases에 자동 업로드
```yaml
# .github/workflows/flutter-build.yml
- name: Build APK
  run: |
    cd mobile
    flutter build apk --release
    
- name: Upload to GitHub Releases
  uses: softprops/action-gh-release@v1
  with:
    files: mobile/build/app/outputs/flutter-apk/app-release.apk
```

**iOS**: Mac 환경 필요 (추후 Mac self-hosted runner 추가 또는 GitHub-hosted macOS runner 사용)

### 8.3 API 버전 관리

```
/api/v1/chat    # 현재 버전
/api/v2/chat    # 향후 버전 (하위 호환 유지)
```

---

## 9. 모니터링 및 운영

### 9.1 Prometheus + Grafana 스택

```yaml
# docker-compose.monitoring.yml
services:
  prometheus:
    image: prom/prometheus:latest
    ports:
      - "9090:9090"
    volumes:
      - ./monitoring/prometheus.yml:/etc/prometheus/prometheus.yml

  grafana:
    image: grafana/grafana:latest
    ports:
      - "3001:3000"
    volumes:
      - grafana_data:/var/lib/grafana

  nvidia-smi-exporter:
    image: utkuozdemir/nvidia_gpu_exporter:latest
    ports:
      - "9835:9835"
    volumes:
      - /usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1:/usr/lib/x86_64-linux-gnu/libnvidia-ml.so.1
```

### 9.2 주요 모니터링 지표

| 지표 | 설명 | 임계값 |
|------|------|--------|
| `gpu_memory_used_bytes` | RTX 3070 VRAM 사용량 | > 7.5GB 경고 |
| `api_response_time_seconds` | API 응답 시간 | > 30s 경고 |
| `inference_tokens_per_second` | 추론 속도 | < 5 tok/s 경고 |
| `active_connections` | 동시 접속 수 | > 10 경고 |
| `error_rate` | API 오류율 | > 5% 경고 |

### 9.3 GPU 메모리 관리 전략

```python
# backend/utils/gpu_manager.py
import torch
import gc

def cleanup_gpu_memory():
    """추론 후 GPU 메모리 정리"""
    if torch.cuda.is_available():
        torch.cuda.empty_cache()
        gc.collect()

def get_gpu_memory_info() -> dict:
    """현재 GPU 메모리 상태 반환"""
    if torch.cuda.is_available():
        allocated = torch.cuda.memory_allocated(0) / 1024**3
        reserved = torch.cuda.memory_reserved(0) / 1024**3
        total = torch.cuda.get_device_properties(0).total_memory / 1024**3
        return {
            "allocated_gb": round(allocated, 2),
            "reserved_gb": round(reserved, 2),
            "total_gb": round(total, 2),
            "free_gb": round(total - reserved, 2)
        }
    return {}
```

---

## 10. 디렉토리 구조

```
llmfit-test/                         # 프로젝트 루트
├── .github/
│   └── workflows/
│       ├── deploy.yml               # main 브랜치 자동 배포
│       ├── test.yml                 # PR 테스트 자동화
│       ├── code-review.yml          # AI 코드 리뷰 에이전트
│       └── flutter-build.yml        # Flutter APK 빌드
│
├── backend/                         # FastAPI 백엔드
│   ├── app/
│   │   ├── main.py                  # FastAPI 앱 진입점
│   │   ├── api/
│   │   │   ├── routes/
│   │   │   │   ├── auth.py
│   │   │   │   ├── chat.py
│   │   │   │   └── rag.py
│   │   │   └── deps.py              # 의존성 주입
│   │   ├── core/
│   │   │   ├── config.py            # 환경 설정
│   │   │   ├── security.py          # JWT 인증
│   │   │   └── database.py          # DB 연결
│   │   ├── models/                  # SQLAlchemy 모델
│   │   ├── schemas/                 # Pydantic 스키마
│   │   └── services/
│   │       ├── inference_service.py # AI 추론 서비스
│   │       └── rag_service.py       # RAG 서비스
│   ├── tests/
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   └── Dockerfile
│
├── inference/                       # AI 추론 서버 (독립 실행)
│   ├── model_loader.py              # AWQ 모델 로더
│   ├── inference_server.py          # FastAPI 추론 서버
│   ├── requirements.txt
│   └── Dockerfile
│
├── frontend/                        # Next.js 웹 앱
│   ├── app/
│   ├── components/
│   ├── lib/
│   ├── public/
│   ├── package.json
│   ├── next.config.ts
│   └── Dockerfile
│
├── mobile/                          # Flutter 앱
│   ├── lib/
│   ├── android/
│   ├── ios/
│   └── pubspec.yaml
│
├── agents/                          # AI 에이전트
│   ├── code_review_agent.py         # 코드 리뷰 에이전트
│   └── requirements.txt
│
├── monitoring/                      # 모니터링 설정
│   ├── prometheus.yml
│   ├── grafana/
│   │   └── dashboards/
│   └── docker-compose.monitoring.yml
│
├── docs/                            # 문서
│   ├── chatbot-project-plan.md      # 본 문서
│   ├── api-spec.md                  # API 명세서
│   └── deployment-guide.md         # 배포 가이드
│
├── scripts/                         # 유틸리티 스크립트
│   ├── setup.sh                     # 초기 환경 설정
│   ├── start-all.sh                 # 전체 서비스 시작
│   └── stop-all.sh                  # 전체 서비스 중지
│
├── .env.example                     # 환경변수 예시
├── .gitignore
├── docker-compose.yml               # 전체 서비스 오케스트레이션
└── README.md
```

---

## 11. 리스크 및 대응 방안

| 리스크 | 영향도 | 대응 방안 |
|--------|--------|-----------|
| RTX 3070 VRAM 부족 (OOM) | 높음 | `max_new_tokens` 제한, 동시 요청 큐 처리, AWQ 4-bit 유지 |
| 추론 속도 저하 (긴 컨텍스트) | 중간 | 컨텍스트 창 4096 토큰 제한, 오래된 히스토리 요약 후 압축 |
| Cloudflare Tunnel 단절 | 중간 | cloudflared 자동 재시작 설정 (systemd/Windows Service) |
| 모델 파일 손상/업데이트 | 낮음 | HuggingFace 캐시 유지, 버전 고정 (`revision` 파라미터) |
| Self-hosted Runner 보안 | 높음 | fork PR에서 Runner 실행 금지, `pull_request_target` 주의 |
| PostgreSQL 데이터 손실 | 높음 | 일일 자동 백업 스크립트, Docker Volume 별도 관리 |

### 11.1 Self-hosted Runner 보안 주의사항

```yaml
# 외부 기여자의 fork PR에서 self-hosted runner가 실행되지 않도록 설정
on:
  pull_request:
    branches: [main]

jobs:
  deploy:
    # 리포지토리 소유자의 PR에서만 실행
    if: github.event.pull_request.head.repo.full_name == github.repository
    runs-on: self-hosted
```

---

## 구현 우선순위 요약

```
Week 1-2:  [Phase 1] AWQ 모델 로드 및 추론 서버 구축
Week 3-4:  [Phase 2] FastAPI 백엔드 + PostgreSQL + ChromaDB
Week 5-6:  [Phase 3] Next.js 웹 UI (스트리밍 채팅)
Week 7:    [Phase 5] Cloudflare Tunnel + GitHub Actions 배포
Week 8:    [CI/CD]   Self-hosted Runner + 코드 리뷰 에이전트
Week 9-11: [Phase 4] Flutter 모바일 앱
Week 12:   [Phase 9] Prometheus + Grafana 모니터링
```

---

*본 계획서는 `solidrust/gemma-2-9b-it-AWQ` 모델과 RTX 3070 8GB 환경에 최적화된 로컬 AI 챗봇 서비스 구축을 위한 실무 가이드입니다.*
