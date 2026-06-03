"""
prompts.py 단위 테스트
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "inference"))

from prompts import build_messages, build_auto_title_messages


class TestBuildMessages:
    def test_no_history_injects_system_prompt(self):
        msgs = build_messages(history=[], user_message="안녕")
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"
        assert "점마 뭐꼬?" in msgs[0]["content"]
        assert "안녕" in msgs[0]["content"]

    def test_history_preserved(self):
        history = [
            {"role": "user", "content": "첫 질문"},
            {"role": "assistant", "content": "첫 답변"},
        ]
        msgs = build_messages(history=history, user_message="두 번째 질문")
        assert msgs[-1] == {"role": "user", "content": "두 번째 질문"}
        # 히스토리 포함
        roles = [m["role"] for m in msgs]
        assert "assistant" in roles

    def test_rag_context_injected(self):
        msgs = build_messages(history=[], user_message="테스트", rag_context="세계관 설명")
        assert "세계관 설명" in msgs[0]["content"]

    def test_user_message_at_end(self):
        msgs = build_messages(
            history=[{"role": "user", "content": "q"}, {"role": "assistant", "content": "a"}],
            user_message="마지막 질문",
        )
        assert msgs[-1]["role"] == "user"
        assert msgs[-1]["content"] == "마지막 질문"


class TestBuildAutoTitleMessages:
    def test_returns_list_with_one_user_message(self):
        msgs = build_auto_title_messages("웹소설 주인공 이름 추천해줘")
        assert isinstance(msgs, list)
        assert len(msgs) == 1
        assert msgs[0]["role"] == "user"

    def test_contains_input_message(self):
        first = "판타지 세계관 설명 부탁드려요"
        msgs = build_auto_title_messages(first)
        assert first in msgs[0]["content"]

    def test_title_instruction_present(self):
        msgs = build_auto_title_messages("아무 메시지")
        content = msgs[0]["content"]
        assert "제목" in content
