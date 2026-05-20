# AI 인프라 폴더 생성 경위 및 필요성 보고서

> **작성일**: 2026-05-16  
> **대상 워크스페이스**: `c:\Users\user\Downloads\gemma2_chatbot`  
> **관련 폴더**: `.agents/`, `.github/`, `.n8nac/`

---

## 목차

1. [개요](#1-개요)
2. [생성 원인 및 과정](#2-생성-원인-및-과정)
3. [각 폴더별 상세 설명](#3-각-폴더별-상세-설명)
4. [생성 이유 및 필요성](#4-생성-이유-및-필요성)
5. [폴더 간 관계 구조](#5-폴더-간-관계-구조)
6. [결론](#6-결론)

---

## 1. 개요

본 워크스페이스는 `solidrust/gemma-2-9b-it-AWQ` 모델을 기반으로 하는 챗봇 서비스 프로젝트이며, 워크플로우 자동화 도구인 **n8n**을 코드로 관리하기 위한 **n8n-as-code(n8nac)** 툴체인이 함께 구성되어 있다.

`.agents/`, `.github/`, `.n8nac/` 세 개의 숨김 폴더는 **`npx --yes n8nac update-ai`** 명령어가 실행되면서 자동 생성되었다. 이 명령어는 n8n-as-code 패키지(버전 **2.1.2**)가 제공하는 AI 컨텍스트 초기화 도구로, AI 에이전트(GitHub Copilot, VS Code Copilot 등)가 이 워크스페이스에서 n8n 워크플로우를 올바르게 다룰 수 있도록 필요한 지식과 지침 파일을 생성하는 역할을 한다.

---

## 2. 생성 원인 및 과정

### 2.1 생성 트리거 명령어

```bash
npx --yes n8nac update-ai
```

이 명령어가 프로젝트 루트(`c:\Users\user\Downloads\gemma2_chatbot`)에서 실행됨으로써 세 개의 폴더와 그 하위 파일들이 일괄 생성되었다.

### 2.2 생성 시각

`.n8nac/ai-context.json` 내 `generatedAt` 필드를 기준으로, 생성 시각은 다음과 같다.

```
2026-05-16T07:05:20.097Z
```

### 2.3 생성 절차 (내부 동작 흐름)

```
npx --yes n8nac update-ai 실행
        │
        ├─ 1. 워크스페이스 루트 탐지 (n8nac-config.json 위치 기준)
        │
        ├─ 2. .n8nac/ai-context.json 생성
        │      └─ 스키마 버전, 서명(signature), n8nac 버전, 생성 시각 기록
        │
        ├─ 3. AGENTS.md 생성 또는 갱신
        │      └─ AI 에이전트용 부트스트랩 컨텍스트 주입
        │         (기존 사용자 지침은 파괴하지 않음)
        │
        ├─ 4. .github/agents/n8n-architect.agent.md 생성
        │      └─ VS Code / GitHub Copilot 전용 에이전트 정의 파일
        │
        └─ 5. .agents/skills/n8n-architect/SKILL.md 생성
               └─ .github/agents 미지원 런타임을 위한 폴백 스킬 파일
```

---

## 3. 각 폴더별 상세 설명

### 3.1 `.n8nac/` 폴더

| 항목 | 내용 |
|------|------|
| 위치 | `.n8nac/ai-context.json` |
| 생성 주체 | `npx --yes n8nac update-ai` |
| 역할 | AI 컨텍스트 스냅샷 저장소 |

#### 파일 내용 (`ai-context.json`)

```json
{
  "schemaVersion": 1,
  "signature": "c1c2c84e94406eca93ee860889f84447605b69de89f9bb8f10bb97061f586694",
  "n8nacVersion": "2.1.2",
  "n8nVersion": "Unknown",
  "generatedAt": "2026-05-16T07:05:20.097Z",
  "reason": "snapshot:startup"
}
```

#### 역할 설명

- **`signature`**: 워크스페이스 고유 식별자로, 컨텍스트 파일의 무결성을 검증하는 데 사용된다.
- **`reason: "snapshot:startup"`**: `update-ai` 명령이 최초 실행(startup) 시점에 스냅샷을 생성했음을 의미한다.
- **`n8nVersion: "Unknown"`**: 현재 워크스페이스에 연결된 n8n 인스턴스가 아직 지정되지 않은 상태를 나타낸다.
- AI 에이전트가 이 파일을 참조하여 워크스페이스의 n8nac 버전 호환성을 확인하는 기준점 역할을 한다.

---

### 3.2 `.github/agents/` 폴더

| 항목 | 내용 |
|------|------|
| 위치 | `.github/agents/n8n-architect.agent.md` |
| 생성 주체 | `npx --yes n8nac update-ai` |
| 역할 | VS Code Copilot / GitHub Copilot 전용 에이전트 정의 |

#### 역할 설명

`.github/agents/` 경로는 **VS Code GitHub Copilot이 자동으로 인식하는 워크스페이스 에이전트 등록 경로**이다. 이 경로에 `*.agent.md` 파일을 배치하면, VS Code Copilot 채팅에서 `@n8n-architect`와 같이 에이전트를 직접 호출할 수 있게 된다.

`n8n-architect.agent.md` 파일의 주요 내용:
- **에이전트 이름**: `n8n-architect`
- **호출 조건**: 사용자가 n8n 워크플로우 생성·편집·검증·동기화·디버깅을 요청할 때
- **컨텍스트 루트 프로토콜**: 명령어를 항상 `c:\Users\user\Downloads\gemma2_chatbot`에서 실행하도록 강제
- **워크플로우 작업 전 필수 절차**: `npx --yes n8nac update-ai` → `AGENTS.md` 읽기 → 환경 상태 확인 순서 지정

---

### 3.3 `.agents/skills/n8n-architect/` 폴더

| 항목 | 내용 |
|------|------|
| 위치 | `.agents/skills/n8n-architect/SKILL.md` |
| 생성 주체 | `npx --yes n8nac update-ai` |
| 역할 | `.github/agents` 미지원 AI 런타임을 위한 폴백 스킬 정의 |

#### 역할 설명

모든 AI 에이전트 런타임이 `.github/agents/` 경로를 지원하는 것은 아니다. 일부 런타임은 `.agents/skills/` 경로에서 스킬(skill) 형태로 지침을 로드한다. `SKILL.md`는 `.github/agents/n8n-architect.agent.md`와 동일한 지침을 담고 있으며, 다음 목적으로 사용된다.

- **호환성 보장**: VS Code Copilot이 아닌 다른 AI 도구(Claude, Cursor 등)에서도 동일한 n8n 작업 지침을 제공
- **이중화(Redundancy)**: `.github/agents/` 파일이 로드되지 않을 경우를 대비한 안전망 역할
- **스킬 등록**: 현재 세션의 Copilot은 이 파일을 `n8n-architect` 스킬로 인식하여 n8n 관련 요청 시 자동 참조

---

## 4. 생성 이유 및 필요성

### 4.1 프로젝트 자동화 기반 구성

본 프로젝트(`gemma2_chatbot`)는 단순한 코드 작성 프로젝트가 아니라, **n8n 워크플로우 자동화**를 핵심 인프라로 활용하는 구조이다. 챗봇 서비스의 CI/CD 파이프라인, 코드 리뷰 에이전트, 배포 자동화 등 다양한 자동화 작업이 n8n 워크플로우로 구현될 예정이다.

이를 코드로 관리(n8n-as-code)하기 위해 AI 에이전트가 올바른 명령어, 올바른 경로, 올바른 순서로 워크플로우를 다룰 수 있도록 지침 파일이 필요하다.

### 4.2 AI 에이전트의 실수 방지

n8n-as-code 환경에서 AI 에이전트가 아무런 지침 없이 작업할 경우 다음과 같은 문제가 발생할 수 있다:

| 위험 | 설명 |
|------|------|
| 잘못된 경로에서 명령 실행 | 컨텍스트 루트 외부에서 n8nac 명령 실행 시 오작동 |
| 설정 파일 직접 수정 | `n8nac-config.json`을 AI가 직접 편집하면 워크스페이스 손상 |
| 마이그레이션 없이 작업 | 워크스페이스 마이그레이션 없이 워크플로우 조작 시 데이터 손실 |
| 환경 정보 오추론 | `AGENTS.md`에서 환경 설정을 추론하면 잘못된 인스턴스에 작업 |

세 개의 폴더와 파일들은 이러한 위험을 방지하기 위한 **AI 행동 지침서**로 기능한다.

### 4.3 AI 도구 독립성(Portability)

`.github/agents/`와 `.agents/skills/` 두 경로를 동시에 유지함으로써, 특정 AI 도구에 종속되지 않는 워크스페이스 환경을 구성한다.

```
AI 런타임
    ├─ VS Code Copilot  →  .github/agents/n8n-architect.agent.md 사용
    ├─ 기타 Copilot 호환 도구  →  AGENTS.md 참조
    └─ 기타 AI 런타임  →  .agents/skills/n8n-architect/SKILL.md 사용
```

### 4.4 워크스페이스 상태 추적

`.n8nac/ai-context.json`은 다음 목적을 위해 존재한다:

1. **버전 호환성 검증**: AI 에이전트가 현재 n8nac 버전(`2.1.2`)에 맞는 지침을 적용하는지 확인
2. **무결성 서명**: 컨텍스트 파일이 위변조되지 않았는지 검증
3. **생성 이력 추적**: 언제, 어떤 이유로 AI 컨텍스트가 초기화되었는지 기록

---

## 5. 폴더 간 관계 구조

```
gemma2_chatbot/                          ← 프로젝트 루트 (컨텍스트 루트)
│
├─ AGENTS.md                             ← AI 에이전트 부트스트랩 진입점
│   └─ n8nac update-ai가 갱신 관리
│
├─ .n8nac/
│   └─ ai-context.json                  ← 워크스페이스 상태 스냅샷
│       └─ 버전, 서명, 생성 시각 포함
│
├─ .github/
│   └─ agents/
│       └─ n8n-architect.agent.md       ← VS Code Copilot 에이전트 등록
│           └─ n8n 작업 전 절차 및 규칙 정의
│
└─ .agents/
    └─ skills/
        └─ n8n-architect/
            └─ SKILL.md                 ← 폴백 스킬 정의 (비VS Code 호환)
                └─ n8n-architect.agent.md와 동일 내용
```

---

## 6. 결론

세 개의 폴더(`.agents/`, `.github/`, `.n8nac/`)는 **단 하나의 명령어(`npx --yes n8nac update-ai`)에 의해 자동 생성**된 AI 인프라 구성 파일들이다. 이들은 n8n-as-code 툴체인이 AI 에이전트와 협력하여 n8n 워크플로우를 안전하고 올바르게 관리할 수 있도록 설계된 필수 구성 요소이다.

### 핵심 요약

| 폴더 | 생성 주체 | 역할 | 삭제 가능 여부 |
|------|-----------|------|----------------|
| `.n8nac/` | `n8nac update-ai` | AI 컨텍스트 스냅샷 저장 | **비권장** (버전 추적 손실) |
| `.github/agents/` | `n8nac update-ai` | VS Code Copilot 에이전트 등록 | **비권장** (에이전트 기능 상실) |
| `.agents/skills/` | `n8nac update-ai` | 폴백 스킬 등록 | **비권장** (다른 AI 도구 호환성 상실) |

이 파일들은 **수동으로 편집하거나 삭제하지 말고**, 갱신이 필요할 때는 반드시 `npx --yes n8nac update-ai` 명령어를 통해 재생성해야 한다.
