# 프로젝트 현황 분석 및 보완 사항 보고서

> **프로젝트**: 점마 뭐꼬? — 웹소설/시나리오 창작 AI 챗봇  
> **작성일**: 2026-05-31  
> **분석 범위**: 전체 코드베이스 (inference/, frontend/, docs/)  
> **기준 계획서**: `docs/chatbot-project-plan.md`

---

## 목차

1. [현황 요약](#1-현황-요약)
2. [구현 완료 항목](#2-구현-완료-항목)
3. [계획 대비 미구현 항목](#3-계획-대비-미구현-항목)
4. [코드 품질 이슈](#4-코드-품질-이슈)
5. [보안 취약점](#5-보안-취약점)
6. [성능 및 안정성 개선사항](#6-성능-및-안정성-개선사항)
7. [보완 우선순위 로드맵](#7-보완-우선순위-로드맵)

---

## 1. 현황 요약

### 1.1 전체 진행률

| 계획 단계 | 항목 수 | 완료 | 미완료 | 진행률 |
|-----------|---------|------|--------|--------|
| Phase 1 — 추론 서버 | 4 | 4 | 0 | ✅ 100% |
| Phase 2 — 백엔드 API | 6 | 3 | 3 | 🔶 50% |
| Phase 3 — 프론트엔드 | 4 | 1 | 3 | 🔶 25% |
| Phase 4 — 모바일 앱 | 3 | 0 | 3 | ❌ 0% |
| Phase 5 — 인프라/DevOps | 5 | 0 | 5 | ❌ 0% |
| **전체** | **22** | **8** | **14** | **36%** |

### 1.2 핵심 성과

- **추론 속도 문제 해결**: AutoAWQ → llama-cpp-python 전환으로 3~8 tok/s → **~22 tok/s** 달성 (약 6배 향상)
- **창작 특화 프롬프트 완성**: 웹소설/시나리오 8가지 장르에 대응하는 시스템 프롬프트 및 퀵 액션 구현
- **SSE 스트리밍 파이프라인**: 백그라운드 스레드 + asyncio Queue → 완전 비동기 스트리밍 완성
- **세션 관리 완성**: SQLite 기반 다중 세션 저장·복원 정상 동작

---

## 2. 구현 완료 항목

### 2.1 inference/ (백엔드)

| 파일 | 상태 | 비고 |
|------|------|------|
| `main.py` | ✅ 완료 | FastAPI, SSE, 세션 CRUD 7개 엔드포인트 |
| `model.py` | ✅ 완료 | llama-cpp-python 싱글턴, CUDA GPU 전체 오프로드 |
| `prompts.py` | ✅ 완료 | Gemma-2 system role 우회, RAG 컨텍스트 주입 구조 |
| `database.py` | ✅ 완료 | aiosqlite 비동기 CRUD, ON DELETE CASCADE |
| `schemas.py` | ✅ 완료 | Pydantic v2, ChatRequest, 세션/메시지 스키마 |

### 2.2 frontend/ (프론트엔드)

| 기능 | 상태 | 비고 |
|------|------|------|
| SSE 스트리밍 수신 | ✅ 완료 | ReadableStream + AbortController |
| 마크다운 렌더링 | ✅ 완료 | marked.js v12 (CDN) |
| 세션 사이드바 | ✅ 완료 | 생성·로드·삭제 |
| 다크 테마 UI | ✅ 완료 | CSS 변수 기반 일관된 디자인 |
| 퀵 액션 8종 | ✅ 완료 | 캐릭터/세계관/장면/대화문/플롯 등 |
| 생성 파라미터 조절 | ✅ 완료 | temperature, max_tokens, repetition_penalty |
| 생성 중단(Stop) | ✅ 완료 | AbortController |
| 작품 설정 컨텍스트 | ✅ 완료 | RAG context textarea |

---

## 3. 계획 대비 미구현 항목

### 3.1 Phase 2 — 백엔드 미완성 항목

#### ❌ RAG (Retrieval-Augmented Generation) 파이프라인 미구현

계획서 Phase 2에 명시된 핵심 기능으로, `schemas.py`에 `rag_context` 필드만 존재하며 실제 벡터 DB 연동은 없음.

```
현재 상태:
  ChatRequest.rag_context: Optional[str]  ← 프론트 textarea에서 직접 주입 (임시방편)

계획 상태:
  사용자 문서 업로드 → ChromaDB 벡터화 → 관련 청크 자동 검색 → 프롬프트 주입
```

**필요 작업**:
- `ChromaDB` 또는 `Qdrant` (로컬 경량) 설치 및 초기화
- `sentence-transformers`로 한국어 임베딩 모델 연동 (`jhgan/ko-sroberta-multitask` 권장)
- 문서 업로드 API (`POST /documents`) 신규 구현
- 쿼리 시 유사도 검색 → top-k 청크 자동 주입 로직

---

#### ❌ 인증(Authentication) 시스템 미구현

계획서에 JWT 인증(`python-jose` + `passlib`)이 명시되어 있으나 현재 모든 API는 인증 없이 공개.

**현재 문제**: 서버가 외부에 노출될 경우 누구나 API 호출 가능.

**필요 작업**:
- `POST /auth/register`, `POST /auth/login` 엔드포인트 추가
- FastAPI `Depends`를 이용한 JWT 미들웨어 적용
- 세션 데이터에 `user_id` 컬럼 추가 (멀티 사용자 격리)

---

#### ❌ 요청 제한(Rate Limiting) 미구현

단일 사용자 로컬 환경이라도, 연속적인 중복 요청이 GPU 과부하를 유발할 수 있음.

**필요 작업**:
- `slowapi` 라이브러리를 이용한 엔드포인트별 rate limit 설정
- `/chat/stream` 에 1 req/5s 수준 제한

---

### 3.2 Phase 3 — 프론트엔드 미완성 항목

#### ❌ Next.js 기반 웹 프론트엔드 미구현

계획서에는 TypeScript + Next.js 14 (App Router) + shadcn/ui + Tailwind CSS 스택이 명시.  
현재는 단일 `index.html` (Vanilla JS) 로 프로토타입 수준 구현.

| 항목 | 계획 | 현재 |
|------|------|------|
| 프레임워크 | Next.js 14 | Vanilla JS (index.html) |
| 언어 | TypeScript | JavaScript |
| UI 라이브러리 | shadcn/ui + Tailwind | 인라인 CSS |
| 상태관리 | Zustand | 전역 변수 |
| 마크다운 | react-markdown | marked.js (CDN) |
| 반응형 | 완전 반응형 | 모바일 사이드바 미노출 |

**평가**: 기능적으로는 동작하나, 유지보수성과 확장성이 크게 부족.

---

#### ❌ 세션 검색 기능 미구현

저장된 세션이 많아질수록 원하는 대화를 찾기 어려움.

**필요 작업**:
- 세션 목록 검색 UI (제목 기반 필터링)
- 백엔드 `GET /sessions?q=검색어` 쿼리 파라미터 지원
- SQLite `LIKE` 쿼리 추가

---

#### ❌ 대화 내보내기(Export) 기능 미구현

창작 보조 도구의 핵심 사용 사례임에도 작성된 내용을 파일로 저장하는 기능 없음.

**필요 작업**:
- 현재 세션 내용을 `.txt` / `.md` 로 다운로드하는 버튼
- 프론트 JS에서 Blob + URL.createObjectURL 활용

---

### 3.3 Phase 4 — 모바일 앱 (0% 미착수)

계획서에 Flutter 3.x 기반 iOS/Android 앱이 포함되어 있으나 전혀 착수하지 않음.

**판단**: 로컬 서버 기반 특성상 모바일 앱보다 PWA(Progressive Web App) 전환이 더 실용적.

| 방향 | 장점 | 단점 |
|------|------|------|
| Flutter 앱 (원계획) | 네이티브 UX | 개발 공수 높음, Cloudflare Tunnel 필수 |
| PWA 전환 (대안) | 브라우저 설치, 오프라인 캐시 | 네이티브 기능 제한 |

---

### 3.4 Phase 5 — 인프라/DevOps (0% 미착수)

#### ❌ Docker / Docker Compose 미구성

```
계획 구성:
  docker-compose.yml
  ├── ai-server (AutoAWQ / llama-cpp)
  ├── backend (FastAPI)
  ├── db (PostgreSQL)
  ├── vector-db (ChromaDB)
  └── cache (Redis)
```

현재는 Python 가상환경에 직접 설치된 상태로, 이식성이 없음.

---

#### ❌ Cloudflare Tunnel 미설정

로컬 서버를 HTTPS로 외부 노출하는 수단이 없어 원격 접속 불가.

**필요 작업**:
```bash
# cloudflared 설치 및 터널 설정
cloudflared tunnel create gemma-chatbot
cloudflared tunnel route dns gemma-chatbot your-domain.com
cloudflared tunnel run gemma-chatbot
```

---

#### ❌ GitHub Actions CI/CD 파이프라인 미구성

`.github/workflows/` 디렉터리 자체가 존재하지 않음.

**필요 작업**:
- `lint.yml`: flake8 / ruff 코드 품질 검사
- `test.yml`: pytest 단위·통합 테스트
- `deploy.yml`: Self-hosted Runner를 통한 자동 배포

---

#### ❌ 모니터링 스택 미구성

Prometheus + Grafana 계획이 있으나 미착수.  
최소한 응답 속도와 GPU 사용률이라도 추적해야 창작 중 성능 저하를 감지 가능.

---

## 4. 코드 품질 이슈

### 4.1 의존성 관리 파일 부재 🚨

```
현재: 의존성 정의 파일 없음
필요: requirements.txt 또는 pyproject.toml
```

**검출된 직접 의존성** (코드 분석 기준):

```txt
# requirements.txt (현재 빠진 파일 — 즉시 생성 필요)
fastapi>=0.110.0
uvicorn[standard]>=0.29.0
pydantic>=2.0
aiosqlite>=0.19.0
llama-cpp-python==0.3.4  # 버전 고정 필수
torch>=2.5.1             # CUDA 버전 별도 설치 필요
```

새 환경에서 재현 불가한 프로젝트 상태.

---

### 4.2 하드코딩된 경로

`model.py`의 GGUF 경로와 `database.py`의 DB 경로가 모두 `Path(__file__).parent.parent`로 하드코딩.

```python
# 현재 (model.py)
GGUF_PATH = str(Path(__file__).parent.parent / "models" / "gemma-2-9b-it-Q4_K_M.gguf")

# 개선: 환경 변수 또는 설정 파일에서 로드
import os
GGUF_PATH = os.getenv("GGUF_MODEL_PATH", str(Path(__file__).parent.parent / "models" / "gemma-2-9b-it-Q4_K_M.gguf"))
```

---

### 4.3 health 엔드포인트의 잘못된 모델명

```python
# main.py 현재 코드 (오류)
@app.get("/health")
async def health():
    return {
        "model": "gemma-2-9b-it-AWQ",   # ← 실제로는 GGUF 모델을 사용 중
        ...
    }
```

실제 사용 모델과 불일치. 운영 중 혼란 유발 가능.

---

### 4.4 모델 로딩 실패 시 예외 처리 부재

```python
# model.py 현재 — GGUF 파일이 없을 때 처리 없음
def _load(self):
    self.model = Llama(model_path=GGUF_PATH, ...)   # FileNotFoundError 발생 시 서버 크래시

# 개선안
def _load(self):
    if not Path(GGUF_PATH).exists():
        raise FileNotFoundError(f"GGUF 모델 파일을 찾을 수 없습니다: {GGUF_PATH}")
    self.model = Llama(model_path=GGUF_PATH, ...)
```

---

### 4.5 세션 삭제 시 confirm() 의존

```javascript
// frontend/index.html
async function deleteSession(id, event) {
  event.stopPropagation();
  if (!confirm('이 대화를 삭제할까요?')) return;  // 브라우저 기본 다이얼로그 사용
```

브라우저 기본 `confirm()` 다이얼로그는 UI와 어울리지 않음. 인라인 확인 UI로 교체 필요.

---

### 4.6 토큰 수 초과 시 처리 없음

컨텍스트 윈도우(n_ctx=8192) 초과 시 llama.cpp는 오래된 토큰을 자동으로 잘라내지만, 사용자에게 이를 알리는 UI 장치가 없음.

**필요 작업**: 메시지 수 또는 추정 토큰 수가 임계값 초과 시 경고 표시.

---

### 4.7 테스트 코드 부재

`tests/` 디렉터리가 없으며 단위 테스트 및 통합 테스트가 전무함.

**최소 필요 테스트**:
```
tests/
├── test_database.py       # CRUD 기능 단위 테스트
├── test_prompts.py        # build_messages() 로직 검증
├── test_schemas.py        # Pydantic 스키마 유효성 검사
└── test_api.py            # FastAPI TestClient 통합 테스트
```

---

## 5. 보안 취약점

### 5.1 CORS 전체 허용 (중간 위험)

```python
# main.py 현재
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],   # ← 모든 출처 허용
    allow_methods=["*"],
    allow_headers=["*"],
)
```

**위험**: 외부 노출 시 CSRF 공격 및 무단 API 호출에 취약.

**개선**:
```python
allow_origins=["http://localhost:8000", "https://your-domain.com"]
```

---

### 5.2 세션 ID 예측 불가능성 확인 필요

`database.py`에서 `uuid.uuid4()` 사용으로 세션 ID는 랜덤이지만, 인증 없이 세션 ID만 알면 타인의 대화에 접근 가능.

```python
# 현재: 인증 없이 세션 ID만으로 접근 가능
GET /sessions/{session_id}/messages  # 누구나 호출 가능
```

---

### 5.3 입력 길이 제한 없음

```python
# schemas.py
class SessionCreate(BaseModel):
    title: str = "새 대화"   # ← 길이 제한 없음

class Message(BaseModel):
    content: str              # ← 길이 제한 없음 (수MB 입력 가능)
```

**개선**:
```python
class Message(BaseModel):
    content: str = Field(..., max_length=10000)

class SessionCreate(BaseModel):
    title: str = Field(default="새 대화", max_length=100)
```

---

### 5.4 SQL 인젝션 — 현재 안전 (확인 완료)

`database.py`는 aiosqlite 파라미터 바인딩(`?` 플레이스홀더)을 올바르게 사용하고 있어 SQL 인젝션 위험 없음. ✅

---

### 5.5 XSS — 부분적 안전

프론트엔드에서 사용자 입력은 `escapeHtml()`로 이스케이프하고 있으나, AI 응답은 `marked.parse()`를 통해 HTML로 직접 렌더링.  
악의적인 마크다운(`<script>`, `javascript:` 링크 등)이 AI 응답에 포함될 경우 XSS 가능.

**개선**:
```javascript
// marked.js에 DOMPurify 추가 (CDN 또는 번들)
import DOMPurify from 'dompurify';
const safeHtml = DOMPurify.sanitize(marked.parse(text));
bubble.innerHTML = safeHtml;
```

---

## 6. 성능 및 안정성 개선사항

### 6.1 모델 워밍업(Warm-up) 미구현

서버 시작 후 첫 번째 추론 요청은 llama.cpp 내부의 CUDA 커널 컴파일로 인해 일반 요청보다 10~20초 더 느림.

**개선**:
```python
# main.py lifespan에 워밍업 추가
async def lifespan(app: FastAPI):
    await init_db()
    gemma = GemmaInference.get_instance()
    # 더미 추론으로 CUDA 커널 사전 컴파일
    list(gemma.stream_generate([{"role": "user", "content": "안녕"}], max_new_tokens=1))
    yield
```

---

### 6.2 DB 연결 풀링 미적용

`database.py`는 함수 호출마다 `aiosqlite.connect()`로 새 연결을 생성하고 닫음.  
고빈도 요청 환경에서 연결 오버헤드가 누적될 수 있음.

**개선**: 애플리케이션 수명주기에서 단일 연결 유지 또는 `aiosqlite` 연결 풀 사용.

---

### 6.3 스트리밍 중단 시 부분 응답 미저장

사용자가 ■ 중지 버튼으로 생성을 취소하면 `AbortController`가 발동되어 스트리밍이 중단됨.  
그러나 현재 `saveExchange()`는 스트리밍이 완료된 후에만 호출되므로, 중단된 경우 부분 응답이 저장되지 않음.

**개선**:
```javascript
// 중지 이후에도 지금까지 수신된 fullResponse를 저장
async function stopGeneration() {
    if (abortController) {
        abortController.abort();
        if (fullResponse && currentSessionId) {
            await saveExchange(lastUserMsg, fullResponse + ' [생성 중단됨]');
        }
    }
}
```

---

### 6.4 메시지 페이지네이션 미구현

세션이 오래 지속되면 `GET /sessions/{id}/messages`가 전체 메시지를 한 번에 반환.  
수천 개의 메시지가 있을 경우 응답 크기 및 파싱 성능 저하.

**개선**:
```python
@app.get("/sessions/{session_id}/messages")
async def get_messages(session_id: str, limit: int = 50, offset: int = 0):
    ...
```

---

### 6.5 SQLite → PostgreSQL 마이그레이션 미고려

계획서의 목표 데이터베이스는 PostgreSQL이나 현재 SQLite 사용.  
단일 사용자 로컬 환경에서는 SQLite로 충분하지만, 외부 노출 및 다중 접속 시 WAL 모드 설정 혹은 PostgreSQL 마이그레이션이 필요.

**단기 완화책**: `PRAGMA journal_mode=WAL;` 설정 추가.

---

## 7. 보완 우선순위 로드맵

### 🔴 즉시 처리 (Critical)

| 번호 | 항목 | 파일 | 예상 공수 |
|------|------|------|-----------|
| C-1 | `requirements.txt` 생성 | (신규) | 30분 |
| C-2 | health 엔드포인트 모델명 수정 | `inference/main.py` | 5분 |
| C-3 | GGUF 파일 없을 때 에러 처리 | `inference/model.py` | 30분 |
| C-4 | Message.content 길이 제한 추가 | `inference/schemas.py` | 10분 |
| C-5 | XSS 방지 — DOMPurify 적용 | `frontend/index.html` | 1시간 |

---

### 🟠 단기 처리 (1~2주, High Priority)

| 번호 | 항목 | 설명 | 예상 공수 |
|------|------|------|-----------|
| H-1 | 대화 내보내기 (.md/.txt) | 창작물 저장 기능 | 2시간 |
| H-2 | 세션 검색 | 제목 기반 필터링 | 3시간 |
| H-3 | 모델 워밍업 | 첫 응답 지연 개선 | 1시간 |
| H-4 | 중단 시 부분 응답 저장 | UX 개선 | 2시간 |
| H-5 | CORS 출처 제한 | 보안 강화 | 30분 |
| H-6 | SQLite WAL 모드 설정 | 안정성 향상 | 30분 |
| H-7 | 환경 변수 기반 설정 (.env) | 이식성 향상 | 2시간 |

---

### 🟡 중기 처리 (2~4주, Medium Priority)

| 번호 | 항목 | 설명 | 예상 공수 |
|------|------|------|-----------|
| M-1 | pytest 단위 테스트 작성 | DB, 스키마, 프롬프트 | 1일 |
| M-2 | RAG 파이프라인 구현 | ChromaDB + 임베딩 | 3~5일 |
| M-3 | Cloudflare Tunnel 설정 | 외부 접근 가능화 | 1일 |
| M-4 | Rate Limiting 추가 | slowapi 적용 | 3시간 |
| M-5 | 자동 세션 제목 생성 | LLM 기반 요약 | 2일 |
| M-6 | 메시지 페이지네이션 | 대용량 세션 대응 | 3시간 |

---

### 🟢 장기 처리 (1개월+, Low Priority)

| 번호 | 항목 | 설명 | 예상 공수 |
|------|------|------|-----------|
| L-1 | JWT 인증 시스템 | 멀티 사용자 지원 | 1주 |
| L-2 | Next.js 프론트엔드 재구축 | TypeScript, shadcn/ui | 2주 |
| L-3 | Docker Compose 구성 | 이식성, 배포 자동화 | 3일 |
| L-4 | GitHub Actions CI/CD | 코드 품질 자동화 | 2일 |
| L-5 | Prometheus + Grafana | GPU/API 모니터링 | 3일 |
| L-6 | PWA 전환 (Flutter 대체) | 모바일 접근성 | 1주 |

---

## 결론

현재 프로젝트는 **Phase 1(AI 추론 서버)를 완전히 완성**하고, 창작 특화 기능(퀵 액션, 시스템 프롬프트, 세션 관리)을 갖춘 프로토타입 수준의 서비스를 완성한 상태입니다.

가장 시급한 보완 사항은:
1. **`requirements.txt` 생성** — 환경 재현 불가 문제 즉시 해결
2. **XSS 방지 (DOMPurify)** — AI 응답 마크다운 렌더링 보안 취약점
3. **대화 내보내기** — 창작 도구로서 가장 빠르게 사용성을 높이는 기능
4. **RAG 파이프라인 구현** — 작품 설정을 실제 벡터 검색으로 활용 (현재는 텍스트 직접 입력 방식)

인프라(Docker, CI/CD, 모니터링)는 개인 로컬 프로젝트 특성상 우선순위를 낮추고, 창작 보조 도구로서의 핵심 기능 완성에 집중하는 것을 권장합니다.
