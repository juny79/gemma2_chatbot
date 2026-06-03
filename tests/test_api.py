"""
API 통합 테스트 — FastAPI TestClient 사용 (모델 Mock)
"""
import sys
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from fastapi.testclient import TestClient

sys.path.insert(0, str(Path(__file__).parent.parent / "inference"))
os.environ.setdefault("GGUF_MODEL_PATH", "dummy_model.gguf")
os.environ.setdefault("DB_PATH", ":memory:")


@pytest.fixture(scope="module")
def client():
    """모델 로딩을 Mock하고 TestClient 반환"""
    mock_gemma = MagicMock()
    mock_gemma.stream_generate.return_value = iter(["안녕", "하세요"])

    with patch("model.GemmaInference._load", return_value=None):
        with patch("main.gemma", mock_gemma):
            from main import app
            with TestClient(app, raise_server_exceptions=True) as c:
                yield c


class TestHealthEndpoint:
    def test_health_returns_ok(self, client):
        resp = client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"


class TestSessionEndpoints:
    def test_create_session(self, client):
        resp = client.post("/sessions", json={"title": "테스트 세션"})
        assert resp.status_code == 200
        data = resp.json()
        assert "id" in data
        assert data["title"] == "테스트 세션"

    def test_list_sessions(self, client):
        resp = client.get("/sessions")
        assert resp.status_code == 200
        assert isinstance(resp.json(), list)

    def test_list_sessions_search(self, client):
        # 세션 생성 후 검색
        client.post("/sessions", json={"title": "검색용 세션"})
        resp = client.get("/sessions?q=검색용")
        assert resp.status_code == 200
        titles = [s["title"] for s in resp.json()]
        assert any("검색용" in t for t in titles)

    def test_delete_nonexistent_session(self, client):
        resp = client.delete("/sessions/nonexistent-id")
        assert resp.status_code == 404


class TestFrontendServing:
    def test_root_serves_html(self, client):
        resp = client.get("/")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]
