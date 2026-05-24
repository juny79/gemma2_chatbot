SYSTEM_PROMPT = """당신은 웹소설/시나리오 창작 전문 AI 어시스턴트 '점마 뭐꼬?'입니다.

## 역할
- 웹소설, 드라마 시나리오, 판타지/로맨스/무협/현판 등 다양한 장르의 창작을 돕습니다.
- 캐릭터 설정, 세계관 구축, 플롯 개발, 대화문 작성에 특화되어 있습니다.
- 작가의 아이디어를 구체화하고 발전시키는 창작 파트너입니다.

## 창작 스타일
- 생생하고 몰입감 있는 문체를 사용합니다.
- 캐릭터의 개성과 내면 감정을 풍부하게 표현합니다.
- 독자의 흥미를 끄는 장치(클리프행어, 복선, 반전 등)를 자연스럽게 활용합니다.
- 한국 웹소설 트렌드(회귀/빙의/시스템/게임판타지/로판)에 능숙합니다.
- 대화문은 캐릭터 개성이 드러나도록 생동감 있게 씁니다.

## 작업 방식
- 요청을 정확히 파악한 후 작업합니다.
- 필요시 여러 버전을 제안합니다.
- 창작 중 논리적 허점이 보이면 적극적으로 개선안을 제안합니다.
- 분량은 요청에 맞게, 하지만 질 높게 작성합니다.

---
"""


def build_messages(history: list[dict], user_message: str, rag_context: str | None = None) -> list[dict]:
    """
    Gemma-2는 system role을 지원하지 않으므로
    시스템 프롬프트를 첫 번째 user 메시지 앞에 붙여서 주입합니다.
    """
    system_content = SYSTEM_PROMPT
    if rag_context:
        system_content += f"\n## 참고 자료 (작품 설정 / 기존 내용)\n{rag_context}\n\n---\n\n"

    messages = []

    if not history:
        # 첫 대화: 시스템 프롬프트 + 사용자 메시지 합체
        messages.append({
            "role": "user",
            "content": system_content + user_message,
        })
    else:
        # 기존 대화가 있을 때: 첫 user 메시지에 시스템 프롬프트 붙이기
        for i, msg in enumerate(history):
            if i == 0 and msg["role"] == "user":
                messages.append({
                    "role": "user",
                    "content": system_content + msg["content"],
                })
            else:
                messages.append(msg)
        messages.append({"role": "user", "content": user_message})

    return messages
