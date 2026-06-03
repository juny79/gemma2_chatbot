"""
schemas.py Pydantic 유효성 검사 단위 테스트
"""
import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).parent.parent / "inference"))

from schemas import (
    Message,
    ChatRequest,
    SessionCreate,
    SaveMessagesRequest,
    AutoTitleRequest,
)


class TestMessage:
    def test_valid(self):
        m = Message(role="user", content="안녕하세요")
        assert m.role == "user"

    def test_empty_content_fails(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="")

    def test_too_long_content_fails(self):
        with pytest.raises(ValidationError):
            Message(role="user", content="x" * 10_001)


class TestChatRequest:
    def test_valid(self):
        req = ChatRequest(messages=[{"role": "user", "content": "테스트"}])
        assert len(req.messages) == 1

    def test_empty_messages_fails(self):
        with pytest.raises(ValidationError):
            ChatRequest(messages=[])

    def test_rag_context_too_long_fails(self):
        with pytest.raises(ValidationError):
            ChatRequest(
                messages=[{"role": "user", "content": "q"}],
                rag_context="x" * 20_001,
            )


class TestSessionCreate:
    def test_default_title(self):
        s = SessionCreate()
        assert s.title == "새 대화"

    def test_empty_title_fails(self):
        with pytest.raises(ValidationError):
            SessionCreate(title="")

    def test_too_long_title_fails(self):
        with pytest.raises(ValidationError):
            SessionCreate(title="a" * 101)


class TestAutoTitleRequest:
    def test_valid(self):
        r = AutoTitleRequest(first_user_message="첫 메시지 내용")
        assert r.first_user_message == "첫 메시지 내용"

    def test_empty_fails(self):
        with pytest.raises(ValidationError):
            AutoTitleRequest(first_user_message="")

    def test_too_long_fails(self):
        with pytest.raises(ValidationError):
            AutoTitleRequest(first_user_message="x" * 2_001)
