# Gemma-2 Chatbot

> RTX 3070 8GB 로컬 GPU에서 `solidrust/gemma-2-9b-it-AWQ` 모델을 활용한 챗봇 웹/앱 서비스

---

## 프로젝트 개요

- **AI 모델**: `solidrust/gemma-2-9b-it-AWQ` (4-bit AWQ 양자화, ~5.5GB VRAM)
- **추론 환경**: 로컬 NVIDIA RTX 3070 8GB + AutoAWQ + PyTorch
- **백엔드**: FastAPI + PostgreSQL + Redis + ChromaDB
- **프론트엔드**: Next.js 14 (TypeScript)
- **모바일**: Flutter 3 (iOS/Android)
- **인프라**: Docker Compose + Cloudflare Tunnel + GitHub Actions

## 문서

| 문서 | 설명 |
|------|------|
| [docs/chatbot-project-plan.md](docs/chatbot-project-plan.md) | 전체 프로젝트 계획서 |
| [docs/tech-stack-guide.md](docs/tech-stack-guide.md) | 기술 스택 종합 가이드 |
| [docs/tech-stack-selection-rationale.md](docs/tech-stack-selection-rationale.md) | 기술 선택 기준 및 근거 |
| [docs/ai-infra-folders-report.md](docs/ai-infra-folders-report.md) | AI 인프라 폴더 구성 보고서 |

## 요구 사항

- NVIDIA GPU (VRAM 8GB 이상)
- CUDA 12.x
- Python 3.11+
- Docker + Docker Compose
- Node.js 20+
- Flutter 3.x

## 라이선스

Apache 2.0
