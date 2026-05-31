# Gemma-2 챗봇 기술 스택 종합 정리
## RTX 3070 8GB 로컬 환경 최적화 가이드

> **대상 환경**: Windows/Linux, NVIDIA RTX 3070 8GB VRAM, 16GB+ RAM  
> **핵심 목표**: 메모리 효율성 + 성능 균형 + 확장성  
> **작성일**: 2026-05-19  

---

## 목차

1. [개요 및 메모리 예산](#1-개요-및-메모리-예산)
2. [AI 추론 계층](#2-ai-추론-계층)
3. [백엔드 API 계층](#3-백엔드-api-계층)
4. [데이터 계층](#4-데이터-계층)
5. [프론트엔드 계층](#5-프론트엔드-계층)
6. [모바일 앱 계층](#7-모바일-앱-계층)
7. [인프라 및 DevOps](#8-인프라-및-devops)
8. [실제 배포 구성](#9-실제-배포-구성)

---

## 1. 개요 및 메모리 예산

### 1.1 VRAM 할당 전략

```
총 VRAM: 8GB
├─ AI 모델 (Gemma-2 4-bit AWQ)     ~5.5 GB
├─ KV Cache (4096 tokens)          ~0.8 GB
├─ Python 런타임 오버헤드           ~0.3 GB
└─ 여유 (긴급용)                   ~0.4 GB
────────────────────────────────────────
   합계: ~7.0 GB (상한선 이하)
```

**주의사항**: 동시 요청이 많거나 배치 처리 시 VRAM 초과 가능 → 배치 크기 제한 필수

### 1.2 시스템 메모리 (RAM) 할당 전략

```
총 RAM: 16GB (권장)
├─ OS + 기본 프로세스             ~3 GB
├─ 백엔드 서버 (FastAPI)          ~1-2 GB
├─ 데이터베이스 (PostgreSQL)      ~1-2 GB
├─ 벡터 DB (ChromaDB)             ~0.5-1 GB
├─ 캐시 (Redis)                   ~0.5-1 GB
├─ 모니터링 (Prometheus/Grafana)  ~0.5-1 GB
└─ 여유                            ~2-3 GB
```

---

## 2. AI 추론 계층

### 2.1 추천 기술 스택 ⭐ (현재 계획서 기반)

| 항목 | 기술 | 버전 | 메모리 | 비고 |
|------|------|------|--------|------|
| **모델** | solidrust/gemma-2-9b-it-AWQ | latest | ~5.5 GB | 4-bit 양자화, RTX 3070 최적화 |
| **추론 라이브러리** | AutoAWQ | ≥0.2.5 | ↑ | AWQ 네이티브 지원 |
| **딥러닝 프레임워크** | PyTorch | ≥2.1 (CUDA 12.x) | 0.3 GB | GPU 연산 최적화 |
| **모델 로딩** | transformers | ≥4.40 | ↑ | HuggingFace 직접 연동 |
| **스트리밍** | TextIteratorStreamer | - | - | 토큰 단위 실시간 스트림 |
| **가속화** | accelerate | ≥0.27 | - | 분산 로딩, 메모리 최적화 |

### 2.2 대체 기술 스택 🔄

#### 옵션 A: 더 가벼운 모델 사용 (메모리 부족 시)

| 기술 | VRAM 사용 | 장점 | 단점 |
|------|-----------|------|------|
| **Mistral-7b-Instruct-AWQ** | ~3.5-4 GB | 매우 가볍고 빠름 | 성능 저하 |
| **Qwen1.5-7b-Chat-GPTQ** | ~3.5-4 GB | 지역화 잘됨 | GPTQ 추론 느림 |
| **Llama-2-7b-Chat-AWQ** | ~3.5-4 GB | 안정적 | 구식 모델 |

#### 옵션 B: Text-Generation-Inference (고성능 필요 시)

```bash
# Docker로 실행 (권장)
docker run --gpus all -p 8001:80 \
  ghcr.io/huggingface/text-generation-inference:latest \
  --model-id solidrust/gemma-2-9b-it-AWQ \
  --quantize awq \
  --max-input-length 1024 \
  --max-total-tokens 2048
```

| 특성 | 값 |
|------|-----|
| 장점 | 높은 처리량, 배치 최적화, 프로덕션급 |
| 단점 | Docker 필수, 복잡한 설정 |
| VRAM 사용 | ~6-6.5 GB (원본과 유사) |
| 추천 시기 | 동시 요청 10개 이상 |

#### 옵션 C: Ollama (간편함 최우선)

```bash
ollama pull gemma:2-9b  # GGUF 포맷 (AWQ 아님, 더 무거움)
ollama serve            # 기본 11434 포트
```

| 특성 | 값 |
|------|-----|
| VRAM 사용 | ~7-8 GB (비효율적) |
| 장점 | 극도로 간단한 설치 및 사용 |
| 단점 | AWQ 미지원, 메모리 낭비 |
| 추천 | 프로토타입/데모 용도만 |

### 2.3 설정 및 최적화

#### 권장 기본 설정 (추론 속도 vs 메모리 균형)

```python
# model_config.py
INFERENCE_CONFIG = {
    "device_map": "cuda",
    "torch_dtype": "auto",  # FP16/BF16 자동 선택
    "load_in_8bit": False,  # AWQ 사용 시 불필요
    "max_new_tokens": 512,
    "temperature": 0.7,
    "top_p": 0.9,
    "top_k": 50,
    "repetition_penalty": 1.0,
    "batch_size": 1,  # RTX 3070: 배치 1-2 권장
}

# KV Cache 최적화 (메모리 절약)
generation_config = {
    "use_cache": True,
    "cache_implementation": "static",  # 고정 크기 캐시
    "max_cache_tokens": 2048,  # 컨텍스트 길이 제한
}
```

---

## 3. 백엔드 API 계층

### 3.1 추천 기술 스택 ⭐

| 항목 | 기술 | 버전 | 메모리 | 비고 |
|------|------|------|--------|------|
| **웹 프레임워크** | FastAPI | ≥0.110 | ~0.3-0.5 GB | 비동기, 타입 안전 |
| **ASGI 서버** | Uvicorn | ≥0.29 | ↑ | 경량 + 멀티워커 지원 |
| **ORM** | SQLAlchemy | ≥2.0 | ~0.1 GB | PostgreSQL 최적화 |
| **인증** | python-jose + passlib | - | - | JWT 기반 |
| **유효성 검사** | Pydantic | v2 | - | FastAPI 내장 |
| **HTTP 클라이언트** | httpx | - | - | 비동기 지원 |
| **웹소켓** | WebSocket (FastAPI 내장) | - | - | 실시간 통신 |
| **로깅** | structlog + python-json-logger | - | - | 구조화된 로그 |

### 3.2 대체 기술 스택 🔄

#### 옵션 A: 극도로 가벼운 구성 (메모리 절약)

| 기술 | 메모리 | 장점 | 단점 |
|------|--------|------|------|
| **Starlette (FastAPI 베이스)** | ~0.2 GB | 더 가벼움 | 기능 제한 |
| **Quart (비동기 Flask)** | ~0.2 GB | Flask 친숙 | 커뮤니티 작음 |
| **ASGI: hypercorn** | ~0.3 GB | 성능 우수 | 설정 복잡 |

#### 옵션 B: 높은 성능 필요 시

| 기술 | 장점 | 단점 |
|------|------|------|
| **FastAPI + Gunicorn (Workers)** | 멀티프로세스 처리 | RAM 사용량 증가 (프로세스당 ~0.3 GB) |
| **FastAPI + Uvicorn (--workers)** | 멀티워커 비동기 | 관리 복잡도 증가 |

#### 권장 세팅 (RTX 3070)

```bash
# 단일 워커 (권장)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1

# 또는 멀티워커 (RAM 충분시)
uvicorn main:app --host 0.0.0.0 --port 8000 --workers 2
```

### 3.3 API 구조 예시

```python
# main.py
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
import asyncio

app = FastAPI(title="Gemma-2 Chatbot API")

class ChatRequest(BaseModel):
    message: str
    temperature: float = 0.7
    max_tokens: int = 512

class ChatResponse(BaseModel):
    role: str
    content: str

@app.post("/chat")
async def chat_stream(request: ChatRequest):
    """스트리밍 응답"""
    async def generate():
        for token in inference_stream(request.message):
            yield f"data: {token}\n\n"
    return StreamingResponse(generate(), media_type="text/event-stream")

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    """웹소켓 실시간 채팅"""
    await websocket.accept()
    try:
        while True:
            data = await websocket.receive_json()
            for token in inference_stream(data["message"]):
                await websocket.send_json({"token": token})
    except Exception as e:
        await websocket.close(code=1000)
```

---

## 4. 데이터 계층

### 4.1 추천 기술 스택 ⭐

| 항목 | 기술 | 용도 | 메모리 | 비고 |
|------|------|------|--------|------|
| **관계형 DB** | PostgreSQL 15 | 사용자, 채팅 히스토리 | ~1-1.5 GB | 안정성, JSON 지원 |
| **벡터 DB** | ChromaDB | RAG 지식 베이스 | ~0.5-1 GB | 가벼움, 임베딩 관리 |
| **임베딩 모델** | sentence-transformers (all-MiniLM-L6-v2) | 텍스트 벡터화 | ~0.1-0.2 GB | 빠르고 가벼움 |
| **캐시** | Redis | 세션, 응답 캐시 | ~0.5-1 GB | 초고속 조회 |

### 4.2 대체 기술 스택 🔄

#### 옵션 A: 데이터베이스 (가벼운 대안)

| 기술 | VRAM | 장점 | 단점 |
|------|------|------|------|
| **SQLite** | ~0 GB | 설정 불필요, 경량 | 동시성 약함, 프로덕션 부적합 |
| **DuckDB** | ~0.1 GB | 분석용 최적화 | 온라인 트랜잭션 부적합 |
| **MySQL 8.0** | ~0.8 GB | PostgreSQL 대안 | 성능 약간 떨어짐 |

#### 옵션 B: 벡터 DB (대안)

| 기술 | 메모리 | 장점 | 단점 |
|------|--------|------|------|
| **Faiss (Meta)** | ~0.2 GB | 고성능, 규모 확장 | 별도 운영 필요 |
| **Milvus** | ~0.5-1 GB | 엔터프라이즈급 | 복잡한 설정 |
| **Pinecone** | 클라우드 | 관리 불필요 | 비용 발생, 인터넷 의존 |

#### 옵션 C: 임베딩 모델 (가벼운 대안)

| 기술 | 모델 크기 | 속도 | 장점 |
|------|-----------|------|------|
| **all-MiniLM-L6-v2** ⭐ | 22MB | 매우 빠름 | 권장 (현재) |
| **all-mpnet-base-v2** | 110MB | 빠름 | 성능 약간 우수 |
| **instructor-base** | 109MB | 보통 | 지시 추종 강함 |
| **bge-small-en-v1.5** | 33MB | 매우 빠름 | 영문 최적화 |

#### 옵션 D: 캐시 (경량 대안)

| 기술 | 메모리 | 장점 | 단점 |
|------|--------|------|------|
| **Redis** ⭐ | ~0.5-1 GB | 초고속, 안정성 | 별도 프로세스 |
| **Python Dict + TTL** | - | 외부 의존 없음 | 단일 프로세스만 |
| **Memcached** | ~0.5 GB | 가벼움 | Redis보다 기능 적음 |

### 4.3 Docker Compose 예시 (권장 구성)

```yaml
version: '3.8'
services:
  postgres:
    image: postgres:15-alpine
    environment:
      POSTGRES_DB: chatbot
      POSTGRES_PASSWORD: secret
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

  redis:
    image: redis:7-alpine
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru

  chromadb:
    image: chromadb/chroma:latest
    ports:
      - "8002:8000"
    volumes:
      - chroma_data:/chroma/data

volumes:
  postgres_data:
  chroma_data:
```

---

## 5. 프론트엔드 계층 (Web)

### 5.1 추천 기술 스택 ⭐

| 항목 | 기술 | 버전 | 역할 |
|------|------|------|------|
| **프레임워크** | Next.js (App Router) | ≥14 | 풀스택 React 프레임워크 |
| **언어** | TypeScript | ≥5 | 타입 안전성 |
| **상태관리** | Zustand | ≥4.x | 경량 상태 관리 |
| **UI 컴포넌트** | shadcn/ui + Tailwind CSS | - | 챗봇 UI 구성 |
| **실시간 스트림** | EventSource (SSE) | - | 토큰 단위 실시간 출력 |
| **마크다운 렌더링** | react-markdown | - | AI 응답 포맷팅 |
| **HTTP 클라이언트** | fetch API 또는 TanStack Query | - | API 통신 |

### 5.2 대체 기술 스택 🔄

#### 옵션 A: 더 가벼운 프레임워크

| 기술 | 번들 크기 | 장점 | 단점 |
|------|----------|------|------|
| **SvelteKit** | ~30KB | 매우 가벼움 | 커뮤니티 작음 |
| **Nuxt 3** | ~50KB | Vue.js 기반 | React 생태계 약함 |
| **Astro** | ~0KB (정적) | 초고속 | 동적 기능 제한 |

#### 옵션 B: 상태관리 대안

| 기술 | 번들 크기 | 학습곡선 | 추천 시나리오 |
|------|----------|----------|--------------|
| **TanStack Query (React Query)** | ~40KB | 중간 | API 상태 관리 중심 |
| **Redux Toolkit** | ~60KB | 높음 | 복잡한 상태 구조 |
| **Pinia** | ~8KB | 낮음 | Vue.js 사용 시 |
| **Jotai** | ~4KB | 낮음 | Zustand 경쟁 제품 |

#### 옵션 C: UI 컴포넌트 라이브러리 대안

| 기술 | 특성 | 파일 크기 |
|------|------|----------|
| **shadcn/ui + Tailwind** ⭐ | 복사-붙여넣기 컴포넌트 | ~30-50KB |
| **Headless UI** | 미니멀, 접근성 중심 | ~15KB |
| **Material-UI (MUI)** | 풍부한 컴포넌트 | ~150KB |
| **DaisyUI** | Tailwind 플러그인 | ~20KB |

### 5.3 추천 구조

```typescript
// app/chat/page.tsx
'use client';

import { useState, useRef, useEffect } from 'react';
import { useChat } from '@/hooks/useChat';

export default function ChatPage() {
  const [messages, setMessages] = useState<Message[]>([]);
  const { streamMessage } = useChat();

  const handleSendMessage = async (content: string) => {
    // 1. 사용자 메시지 추가
    setMessages(prev => [...prev, { role: 'user', content }]);

    // 2. 스트리밍 응답 수신
    let fullResponse = '';
    await streamMessage(content, (token) => {
      fullResponse += token;
      setMessages(prev => [
        ...prev.slice(0, -1),
        { role: 'assistant', content: fullResponse }
      ]);
    });
  };

  return (
    <div className="flex flex-col h-screen">
      <ChatMessages messages={messages} />
      <ChatInput onSend={handleSendMessage} />
    </div>
  );
}

// hooks/useChat.ts
export function useChat() {
  const streamMessage = async (
    message: string,
    onToken: (token: string) => void
  ) => {
    const response = await fetch('/api/chat', {
      method: 'POST',
      body: JSON.stringify({ message }),
    });

    const reader = response.body?.getReader();
    const decoder = new TextDecoder();

    while (true) {
      const { value, done } = await reader!.read();
      if (done) break;

      const chunk = decoder.decode(value);
      const lines = chunk.split('\n');
      
      for (const line of lines) {
        if (line.startsWith('data: ')) {
          const token = line.slice(6);
          onToken(token);
        }
      }
    }
  };

  return { streamMessage };
}
```

---

## 6. 모바일 앱 계층

### 6.1 추천 기술 스택 ⭐

| 항목 | 기술 | 용도 |
|------|------|------|
| **프레임워크** | Flutter 3.x | Android/iOS 크로스플랫폼 |
| **언어** | Dart | 앱 로직 |
| **HTTP 통신** | dio | RESTful API 호출 |
| **상태관리** | Riverpod | 반응형 상태 관리 |
| **로컬 저장소** | flutter_secure_storage | 토큰 보안 저장 |
| **UI 컴포넌트** | Flutter Material 3 | 기본 디자인 |

### 6.2 대체 기술 스택 🔄

#### 옵션 A: 크로스플랫폼

| 기술 | 성능 | 학습곡선 | 번들 크기 |
|------|------|----------|----------|
| **Flutter 3.x** ⭐ | 최우수 | 중간 | ~25-40MB |
| **React Native** | 중간 | 낮음 | ~35-50MB |
| **Xamarin** | 중간 | 높음 | ~40-60MB |

#### 옵션 B: 단일 플랫폼

| 기술 | 성능 | 이유 |
|------|------|------|
| **Swift (iOS)** | 최고 | iOS만 필요시 |
| **Kotlin (Android)** | 최고 | Android만 필요시 |

### 6.3 추천 구조

```dart
// lib/main.dart
import 'package:flutter/material.dart';
import 'package:riverpod_flutter_hooks/riverpod_flutter_hooks.dart';

void main() => runApp(const ProviderScope(child: MyApp()));

class MyApp extends ConsumerWidget {
  const MyApp();

  @override
  Widget build(BuildContext context, WidgetRef ref) {
    return MaterialApp(
      home: ChatScreen(),
    );
  }
}

// lib/screens/chat_screen.dart
class ChatScreen extends ConsumerWidget {
  @override
  Widget build(BuildContext context, WidgetRef ref) {
    final messages = ref.watch(chatMessagesProvider);
    final chatService = ref.watch(chatServiceProvider);

    return Scaffold(
      appBar: AppBar(title: const Text('Gemma-2 Chatbot')),
      body: Column(
        children: [
          Expanded(
            child: ListView.builder(
              itemCount: messages.length,
              itemBuilder: (context, index) => ChatBubble(
                message: messages[index],
              ),
            ),
          ),
          ChatInput(
            onSend: (message) async {
              await chatService.sendMessage(message);
            },
          ),
        ],
      ),
    );
  }
}

// lib/providers/chat_service.dart
final chatServiceProvider = Provider((ref) => ChatService(
  apiClient: ref.watch(apiClientProvider),
));

class ChatService {
  final DioClient apiClient;

  ChatService({required this.apiClient});

  Future<void> sendMessage(String message) async {
    try {
      final response = await apiClient.post(
        '/chat',
        data: {'message': message},
      );
      // 처리...
    } catch (e) {
      // 오류 처리...
    }
  }
}
```

---

## 7. 인프라 및 DevOps

### 7.1 추천 기술 스택 ⭐

| 항목 | 기술 | 용도 | 필수 여부 |
|------|------|------|----------|
| **외부 터널링** | Cloudflare Tunnel (cloudflared) | 로컬 → HTTPS 노출 | ✅ 필수 |
| **컨테이너** | Docker + Docker Compose | 서비스 격리/재현성 | ⭐ 권장 |
| **CI/CD** | GitHub Actions + Self-hosted Runner | 자동 빌드/배포/테스트 | ✅ 필수 |
| **에이전트 프레임워크** | LangChain | AI 코드 리뷰 에이전트 | ⭐ 계획됨 |
| **모니터링 (선택)** | Prometheus + Grafana | GPU/API 지표 수집 | ❌ 선택 |
| **로그 (선택)** | Loki + Promtail | 중앙 로그 관리 | ❌ 선택 |

### 7.2 대체 기술 스택 🔄

#### 옵션 A: 외부 노출 (대안)

| 기술 | 비용 | 설정 난이도 | 추천 |
|------|------|-----------|------|
| **Cloudflare Tunnel** ⭐ | 무료 | 낮음 | 권장 |
| **ngrok** | 무료/유료 | 낮음 | 개발용 |
| **Frp (Fast Reverse Proxy)** | 무료 | 중간 | 자체 서버 필요 |
| **SSH 터널** | 무료 | 높음 | 임시 용도만 |

#### 옵션 B: 로깅 및 모니터링 (라이트 구성)

| 구성 | 메모리 | 설정 | 추천 |
|------|--------|------|------|
| **없음 (간단한 파일 로그)** | ~0 | 매우 낮음 | 초기 단계 |
| **structlog + 파일 저장** | ~0 | 낮음 | MVP |
| **ELK Stack (Elasticsearch + Logstash + Kibana)** | ~2-3 GB | 높음 | 프로덕션 |
| **Grafana Loki (경량)** | ~0.5 GB | 중간 | 권장 |

#### 옵션 C: 오케스트레이션 (선택)

| 기술 | 복잡도 | 메모리 | 추천 시나리오 |
|------|--------|--------|--------------|
| **Docker Compose** ⭐ | 낮음 | ~2-3 GB | 현재 (단일 PC) |
| **Kubernetes (Kind)** | 높음 | ~4-5 GB | 마이크로서비스 |
| **Podman** | 낮음 | ~1.5-2 GB | Docker 대안 |

### 7.3 권장 배포 구성 (Docker Compose)

```yaml
version: '3.8'

services:
  # 1. AI 추론 서버
  inference:
    build:
      context: ./inference
      dockerfile: Dockerfile
    container_name: gemma-inference
    environment:
      CUDA_VISIBLE_DEVICES: "0"
      MODEL_ID: "solidrust/gemma-2-9b-it-AWQ"
    ports:
      - "8001:8000"
    volumes:
      - huggingface_cache:/root/.cache/huggingface
      - ./inference:/app
    deploy:
      resources:
        reservations:
          devices:
            - driver: nvidia
              count: 1
              capabilities: [gpu]
    restart: unless-stopped

  # 2. 백엔드 API
  backend:
    build:
      context: ./backend
      dockerfile: Dockerfile
    container_name: gemma-backend
    environment:
      DATABASE_URL: "postgresql://user:password@postgres:5432/chatbot"
      REDIS_URL: "redis://redis:6379"
      INFERENCE_URL: "http://inference:8000"
    ports:
      - "8000:8000"
    depends_on:
      - postgres
      - redis
      - inference
    volumes:
      - ./backend:/app
    restart: unless-stopped

  # 3. 프론트엔드
  frontend:
    build:
      context: ./frontend
      dockerfile: Dockerfile
    container_name: gemma-frontend
    environment:
      NEXT_PUBLIC_API_URL: "http://localhost:8000"
    ports:
      - "3000:3000"
    depends_on:
      - backend
    volumes:
      - ./frontend:/app
      - /app/.next
    restart: unless-stopped

  # 4. PostgreSQL
  postgres:
    image: postgres:15-alpine
    container_name: gemma-postgres
    environment:
      POSTGRES_DB: chatbot
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data
    restart: unless-stopped

  # 5. Redis
  redis:
    image: redis:7-alpine
    container_name: gemma-redis
    ports:
      - "6379:6379"
    command: redis-server --maxmemory 1gb --maxmemory-policy allkeys-lru
    restart: unless-stopped

  # 6. ChromaDB
  chromadb:
    image: chromadb/chroma:latest
    container_name: gemma-chromadb
    ports:
      - "8002:8000"
    volumes:
      - chroma_data:/chroma/data
    restart: unless-stopped

volumes:
  postgres_data:
  chroma_data:
  huggingface_cache:

networks:
  default:
    name: gemma-network
```

```dockerfile
# inference/Dockerfile
FROM nvidia/cuda:12.1.1-devel-ubuntu22.04

WORKDIR /app

RUN apt-get update && apt-get install -y python3-pip python3-dev

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8000

CMD ["python3", "main.py"]
```

---

## 8. 실제 배포 구성

### 8.1 최소 구성 (MVP)

```
필수 요소만:
├─ Inference Server (Gemma-2 + FastAPI)
├─ PostgreSQL (히스토리 저장)
├─ Next.js Frontend
└─ Cloudflare Tunnel
```

**메모리 사용**: ~8 GB VRAM + ~10 GB RAM

### 8.2 권장 구성 (프로덕션)

```
전체 구성:
├─ Inference Server (AutoAWQ + FastAPI)
├─ Backend API Gateway (FastAPI)
├─ PostgreSQL (데이터 베이스)
├─ Redis (캐시/세션)
├─ ChromaDB (RAG 벡터 DB)
├─ Next.js Frontend (Web)
├─ Flutter App (Mobile)
├─ Cloudflare Tunnel (외부 노출)
├─ GitHub Actions CI/CD
├─ LangChain 코드 리뷰 에이전트
└─ Prometheus/Grafana (모니터링)
```

**메모리 사용**: ~8 GB VRAM + ~15 GB RAM

### 8.3 설치 순서 (체크리스트)

#### Phase 1: 기초 인프라 (1주)
- [ ] Docker + Docker Compose 설치
- [ ] Cloudflare Tunnel 설정
- [ ] GitHub Actions Self-hosted Runner 등록

#### Phase 2: AI 추론 서버 (1~2주)
- [ ] PyTorch + CUDA 설정
- [ ] AutoAWQ 설치
- [ ] Gemma-2 모델 다운로드 테스트
- [ ] FastAPI 추론 서버 구현

#### Phase 3: 백엔드 (2주)
- [ ] PostgreSQL 세팅
- [ ] FastAPI 백엔드 서버 구현
- [ ] JWT 인증 구현
- [ ] WebSocket 실시간 채팅

#### Phase 4: 프론트엔드 (2주)
- [ ] Next.js 프로젝트 생성
- [ ] 챗봇 UI 컴포넌트 개발
- [ ] SSE 스트리밍 구현
- [ ] 마크다운 렌더링

#### Phase 5: 모바일 앱 (3주)
- [ ] Flutter 프로젝트 생성
- [ ] API 통신 구현
- [ ] 토큰 보안 저장
- [ ] iOS/Android 빌드

#### Phase 6: 자동화 및 모니터링 (2주)
- [ ] GitHub Actions 워크플로우
- [ ] LangChain 코드 리뷰 에이전트
- [ ] Prometheus/Grafana 모니터링 (선택)

---

## 9. 최종 권장 요약

### RTX 3070 8GB 환경에서 최적 구성

```
🎯 AI 추론층
  └─ AutoAWQ + Transformers (Gemma-2 4-bit AWQ)
     대체: Text-Generation-Inference 또는 Ollama

🎯 백엔드층
  └─ FastAPI + Uvicorn (단일 워커)
     대체: Starlette 또는 Quart

🎯 데이터층
  ├─ PostgreSQL 15
  ├─ ChromaDB (sentence-transformers 임베딩)
  └─ Redis (캐시)
     대체: SQLite, Faiss, Memcached

🎯 프론트엔드층 (Web)
  └─ Next.js 14 + TypeScript + Zustand + shadcn/ui
     대체: SvelteKit 또는 Nuxt 3

🎯 모바일층
  └─ Flutter 3 + Riverpod + dio
     대체: React Native 또는 단일 플랫폼 (Swift/Kotlin)

🎯 인프라층
  ├─ Docker Compose (로컬 통합)
  ├─ Cloudflare Tunnel (외부 노출)
  ├─ GitHub Actions Self-hosted Runner (CI/CD)
  ├─ LangChain (코드 리뷰 에이전트)
  └─ Prometheus/Grafana (선택)
```

### 메모리 효율성 팁

```
VRAM 절약:
  ✅ 배치 크기 제한 (배치_크기 = 1-2)
  ✅ max_new_tokens 제한 (512 권장)
  ✅ KV Cache 고정 크기 사용
  ✅ AWQ 양자화 모델 선택

RAM 절약:
  ✅ 불필요한 모니터링 도구 제외 (초기 단계)
  ✅ Redis maxmemory 제한 (1GB 권장)
  ✅ 단일 워커 Uvicorn 사용
  ✅ 정기적인 메모리 프로파일링
```

---

**이 문서는 n8n 자동화 인프라를 보유한 상태에서, RTX 3070 8GB로 Gemma-2 챗봇을 구축하기 위한 실전 가이드입니다. 필요시 대체 기술을 선택하여 유연하게 구성할 수 있습니다.**
