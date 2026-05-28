# 점마뭐꼬? — 웹소설·시나리오 창작 에이전트

> RTX 3070 8GB 로컬 GPU에서 `gemma-2-9b-it-Q4_K_M.gguf` (GGUF/llama.cpp) 모델을 활용한  
> **웹소설·드라마 시나리오 창작 전문 AI 챗봇**

---

## 프로젝트 개요

"점마뭐꼬?"는 작가의 창작 파트너를 목표로 하는 로컬 AI 에이전트입니다.  
캐릭터 설정·세계관 구축·플롯 개발·대화문 작성에 특화된 시스템 프롬프트를 탑재하고,  
SSE(Server-Sent Events) 스트리밍으로 토큰을 실시간 출력합니다.

---

## 핵심 기능 (현재 구현 완료)

| 기능 | 설명 |
|------|------|
| **SSE 스트리밍 채팅** | `/chat/stream` POST → `text/event-stream` 토큰 단위 실시간 출력 |
| **시나리오 시스템 프롬프트** | 웹소설/드라마/판타지/로맨스/무협 등 장르 창작 특화 페르소나 |
| **대화 세션 관리** | 세션 생성·조회·제목 수정·삭제 (SQLite, 비동기 aiosqlite) |
| **대화 히스토리 유지** | 멀티턴 컨텍스트 — 시스템 프롬프트를 첫 user 메시지에 주입하는 방식으로 Gemma-2 호환 |
| **RAG 컨텍스트 주입 준비** | `ChatRequest.rag_context` 필드 → 시스템 프롬프트에 참고 자료 삽입 (Phase 2) |
| **웹 UI (SPA)** | 단일 HTML 파일, 다크 테마, Markdown 렌더링, 세션 사이드바 |

---

## 아키텍처

```
┌──────────────────────────────────────────────────────┐
│                  Browser (frontend/)                  │
│   index.html — 다크 테마 SPA (Vanilla JS + CSS)       │
│   • 세션 목록 사이드바                                  │
│   • SSE ReadableStream 수신 → 마크다운 렌더링           │
└────────────────────────┬─────────────────────────────┘
                         │ HTTP / SSE
┌────────────────────────▼─────────────────────────────┐
│              FastAPI 백엔드 (inference/)               │
│                                                       │
│  main.py                                              │
│  ├── GET  /            (frontend/index.html 서빙)     │
│  ├── GET  /health      (모델 로드 상태 확인)            │
│  ├── POST /sessions                                   │
│  ├── GET  /sessions                                   │
│  ├── GET  /sessions/{id}/messages                     │
│  ├── POST /sessions/{id}/messages                     │
│  ├── PATCH/sessions/{id}/title                        │
│  ├── DELETE /sessions/{id}                            │
│  └── POST /chat/stream  ← SSE 스트리밍 핵심 엔드포인트 │
│                                                       │
│  prompts.py — 시나리오 에이전트 시스템 프롬프트 + 메시지  │
│               빌더 (Gemma-2 system role 우회 처리)     │
│                                                       │
│  model.py  — GemmaInference 싱글턴                    │
│              llama-cpp-python + CUDA 전체 GPU 오프로드  │
│              (n_gpu_layers=-1, n_ctx=8192)             │
│                                                       │
│  database.py — aiosqlite 비동기 CRUD                  │
│  schemas.py  — Pydantic 요청/응답 스키마               │
└────────────────────────┬─────────────────────────────┘
                         │ aiosqlite
┌────────────────────────▼─────────────────────────────┐
│           SQLite DB  (data/chatbot.db)                │
│   sessions  — id(UUID), title, created_at, updated_at │
│   messages  — id, session_id, role, content, created_at│
└──────────────────────────────────────────────────────┘
                         │ llama-cpp-python
┌────────────────────────▼─────────────────────────────┐
│          AI 모델 (models/)                             │
│   gemma-2-9b-it-Q4_K_M.gguf  ← 현재 사용 (llama.cpp) │
│   gemma-2-9b-it-AWQ/          ← 예비 (AutoAWQ)        │
│   NVIDIA RTX 3070 8GB / CUDA 12.x                    │
└──────────────────────────────────────────────────────┘
```

---

## 디렉터리 구조

```
gemma2_chatbot/
├── inference/
│   ├── main.py        # FastAPI 앱, 라우터, SSE 스트리밍
│   ├── model.py       # GemmaInference 싱글턴 (llama-cpp-python)
│   ├── prompts.py     # 시나리오 에이전트 시스템 프롬프트 + 메시지 빌더
│   ├── database.py    # aiosqlite 기반 세션/메시지 CRUD
│   └── schemas.py     # Pydantic 스키마
├── frontend/
│   └── index.html     # 다크 테마 SPA (Vanilla JS, 세션 사이드바, 마크다운)
├── models/
│   ├── gemma-2-9b-it-Q4_K_M.gguf      # 현재 추론 모델
│   └── gemma-2-9b-it-AWQ/             # AWQ 예비 모델
├── data/
│   └── chatbot.db     # SQLite DB (자동 생성)
└── docs/              # 기획·기술 문서
```

---

## 기술 스택

| 영역 | 기술 |
|------|------|
| AI 추론 | `llama-cpp-python` (GGUF, CUDA 전체 오프로드) |
| AI 모델 | Gemma-2 9B Instruct Q4_K_M (GGUF) |
| 백엔드 | FastAPI, aiosqlite, Pydantic v2 |
| 프론트엔드 | Vanilla HTML/CSS/JS (SPA), SSE ReadableStream |
| DB | SQLite (`data/chatbot.db`) |
| GPU | NVIDIA RTX 3070 8GB / CUDA 12.x |
| Python | 3.11+ |

---

## 진행 현황

### ✅ Phase 1 — 로컬 추론 서버 (완료)

- [x] GGUF 모델 로드 (llama-cpp-python, CUDA 전체 GPU 오프로드)
- [x] FastAPI SSE 스트리밍 채팅 엔드포인트
- [x] 시나리오 에이전트 시스템 프롬프트 (웹소설/시나리오 창작 특화)
- [x] Gemma-2 system role 미지원 우회 처리 (첫 user 메시지에 삽입)
- [x] 멀티턴 대화 히스토리 관리
- [x] SQLite 기반 세션/메시지 영속성 (비동기 CRUD)
- [x] 다크 테마 웹 UI (마크다운 렌더링, 세션 사이드바)
- [x] `ChatRequest.rag_context` 필드 — RAG 연동 인터페이스 예약

### 🔲 Phase 2 — RAG & 고도화 (예정)

- [ ] ChromaDB 기반 RAG (작품 설정·기존 원고 벡터 검색)
- [ ] 대화 자동 요약 → 장기 메모리 압축
- [ ] PostgreSQL 마이그레이션 (SQLite → 프로덕션 DB)
- [ ] Redis 캐시 레이어

### 🔲 Phase 3 — 배포 & 확장 (예정)

- [ ] Docker Compose 패키징
- [ ] Cloudflare Tunnel 원격 접근
- [ ] Next.js 14 프론트엔드 리빌드 (TypeScript)
- [ ] Flutter 모바일 앱 (iOS/Android)
- [ ] GitHub Actions CI/CD

---

## 빠른 시작

```bash
# 의존성 설치 (CUDA 빌드 llama-cpp-python 필요)
pip install fastapi uvicorn aiosqlite pydantic

# llama-cpp-python CUDA 빌드
pip install llama-cpp-python --extra-index-url https://abetlen.github.io/llama-cpp-python/whl/cu124

# 서버 실행
cd inference
uvicorn main:app --host 0.0.0.0 --port 8000 --reload
```

서버 기동 후 브라우저에서 `http://localhost:8000` 접속

---

## 문서

| 문서 | 설명 |
|------|------|
| [docs/chatbot-project-plan.md](docs/chatbot-project-plan.md) | 전체 프로젝트 계획서 |
| [docs/tech-stack-guide.md](docs/tech-stack-guide.md) | 기술 스택 종합 가이드 |
| [docs/tech-stack-selection-rationale.md](docs/tech-stack-selection-rationale.md) | 기술 선택 기준 및 근거 |
| [docs/ai-infra-folders-report.md](docs/ai-infra-folders-report.md) | AI 인프라 폴더 구성 보고서 |
| [docs/inference-speed-analysis-report.md](docs/inference-speed-analysis-report.md) | 추론 속도 분석 보고서 |

---

## 라이선스

Apache 2.0
