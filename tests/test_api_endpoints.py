"""
BizScout API — Integration Tests for ALL Endpoints (Schnittstellen)
===================================================================
Tests every API endpoint contract with mocked external services.
Run before every push: python -m pytest tests/ -v

Endpoints covered:
  GET  /health              → Health check + DB connectivity
  POST /search              → Perplexity search
  POST /research            → Perplexity + Claude pipeline
  POST /chat                → Claude chat with memory
  GET  /sessions            → List all sessions
  GET  /sessions/{id}/msgs  → Get session messages
  DELETE /sessions/{id}     → Delete a session
"""
import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine, async_sessionmaker

from app.main import app
from app.database import Base, get_db


# ═══════════════════════════════════════════════════════════════════════════════
# TEST DATABASE SETUP (SQLite in-memory — no PostgreSQL needed)
# ═══════════════════════════════════════════════════════════════════════════════

TEST_DB_URL = "sqlite+aiosqlite:///./test_bizscout.db"

test_engine = create_async_engine(
    TEST_DB_URL,
    echo=False,
    connect_args={"check_same_thread": False},
)

# Enable foreign key enforcement for SQLite (CASCADE support)
from sqlalchemy import event

@event.listens_for(test_engine.sync_engine, "connect")
def set_sqlite_pragma(dbapi_connection, connection_record):
    cursor = dbapi_connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()

TestSessionLocal = async_sessionmaker(test_engine, class_=AsyncSession, expire_on_commit=False)


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


# Override the DB dependency
app.dependency_overrides[get_db] = override_get_db


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    """Create tables before each test, drop after."""
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def client():
    """Async test client for the FastAPI app."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ═══════════════════════════════════════════════════════════════════════════════
# 1. HEALTH ENDPOINT
# ═══════════════════════════════════════════════════════════════════════════════

class TestHealthEndpoint:

    @pytest.mark.asyncio
    async def test_health_returns_ok(self, client):
        """GET /health → 200, status=ok, database=connected"""
        resp = await client.get("/health")
        assert resp.status_code == 200
        data = resp.json()
        assert data["status"] == "ok"
        assert data["service"] == "BizScout API"
        assert data["database"] == "connected"

    @pytest.mark.asyncio
    async def test_health_response_schema(self, client):
        """Health response must have exactly 3 keys."""
        resp = await client.get("/health")
        data = resp.json()
        assert set(data.keys()) == {"status", "service", "database"}


# ═══════════════════════════════════════════════════════════════════════════════
# 2. SEARCH ENDPOINT (Perplexity)
# ═══════════════════════════════════════════════════════════════════════════════

MOCK_PERPLEXITY_RESULT = {
    "answer": "Berlin hat über 8.000 Restaurants.",
    "sources": ["https://source1.de", "https://source2.de"],
    "mode": "restaurants",
}


class TestSearchEndpoint:

    @pytest.mark.asyncio
    @patch("app.routers.search.search_perplexity", new_callable=AsyncMock)
    async def test_search_basic(self, mock_pplx, client):
        """POST /search → 200, returns answer/sources/mode."""
        mock_pplx.return_value = MOCK_PERPLEXITY_RESULT

        resp = await client.post("/search", json={"query": "Restaurants Berlin", "mode": "restaurants"})
        assert resp.status_code == 200

        data = resp.json()
        assert "answer" in data
        assert "sources" in data
        assert "mode" in data
        assert data["mode"] == "restaurants"
        assert isinstance(data["sources"], list)

    @pytest.mark.asyncio
    @patch("app.routers.search.search_perplexity", new_callable=AsyncMock)
    async def test_search_default_mode(self, mock_pplx, client):
        """POST /search without mode defaults to 'general'."""
        mock_pplx.return_value = {**MOCK_PERPLEXITY_RESULT, "mode": "general"}

        resp = await client.post("/search", json={"query": "test"})
        assert resp.status_code == 200
        assert resp.json()["mode"] == "general"

    @pytest.mark.asyncio
    async def test_search_missing_query(self, client):
        """POST /search without query → 422 validation error."""
        resp = await client.post("/search", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @patch("app.routers.search.search_perplexity", new_callable=AsyncMock)
    async def test_search_all_modes(self, mock_pplx, client):
        """All 8 search modes should be accepted."""
        modes = ["restaurants", "events", "hotels", "messen", "zeitarbeit", "akquise", "markt", "general"]
        for mode in modes:
            mock_pplx.return_value = {**MOCK_PERPLEXITY_RESULT, "mode": mode}
            resp = await client.post("/search", json={"query": "test", "mode": mode})
            assert resp.status_code == 200, f"Mode '{mode}' failed with {resp.status_code}"


# ═══════════════════════════════════════════════════════════════════════════════
# 3. RESEARCH ENDPOINT (Perplexity + Claude)
# ═══════════════════════════════════════════════════════════════════════════════

class TestResearchEndpoint:

    @pytest.mark.asyncio
    @patch("app.routers.research.ask_claude", new_callable=AsyncMock)
    @patch("app.routers.research.search_perplexity", new_callable=AsyncMock)
    async def test_research_basic(self, mock_pplx, mock_claude, client):
        """POST /research → 200, returns search_summary + ai_analysis + sources + mode."""
        mock_pplx.return_value = MOCK_PERPLEXITY_RESULT
        mock_claude.return_value = "**Analyse:** Berlin wächst im Gastro-Bereich."

        resp = await client.post("/research", json={"query": "Gastro Berlin", "mode": "restaurants"})
        assert resp.status_code == 200

        data = resp.json()
        assert "search_summary" in data
        assert "ai_analysis" in data
        assert "sources" in data
        assert "mode" in data
        assert data["mode"] == "restaurants"

    @pytest.mark.asyncio
    @patch("app.routers.research.ask_claude", new_callable=AsyncMock)
    @patch("app.routers.research.search_perplexity", new_callable=AsyncMock)
    async def test_research_claude_receives_perplexity_data(self, mock_pplx, mock_claude, client):
        """Claude should receive the Perplexity search results as context."""
        mock_pplx.return_value = MOCK_PERPLEXITY_RESULT
        mock_claude.return_value = "Analyse."

        await client.post("/research", json={"query": "test"})

        # Verify Claude was called with the Perplexity summary
        call_args = mock_claude.call_args[0][0]
        assert len(call_args) == 1
        assert call_args[0]["role"] == "user"
        assert MOCK_PERPLEXITY_RESULT["answer"] in call_args[0]["content"]

    @pytest.mark.asyncio
    @patch("app.routers.research.search_perplexity", new_callable=AsyncMock)
    async def test_research_perplexity_failure(self, mock_pplx, client):
        """If Perplexity fails → 502."""
        mock_pplx.side_effect = Exception("API down")

        resp = await client.post("/research", json={"query": "test"})
        assert resp.status_code == 502

    @pytest.mark.asyncio
    async def test_research_missing_query(self, client):
        """POST /research without query → 422."""
        resp = await client.post("/research", json={})
        assert resp.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# 4. CHAT ENDPOINT (Claude + Memory)
# ═══════════════════════════════════════════════════════════════════════════════

class TestChatEndpoint:

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_chat_new_session(self, mock_claude, client):
        """POST /chat without session_id → creates new session, returns answer + session_id."""
        mock_claude.return_value = "Hallo! Wie kann ich helfen?"

        resp = await client.post("/chat", json={"message": "Hallo"})
        assert resp.status_code == 200

        data = resp.json()
        assert "answer" in data
        assert "session_id" in data
        assert len(data["session_id"]) > 0  # UUID
        assert data["answer"] == "Hallo! Wie kann ich helfen?"

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_chat_continue_session(self, mock_claude, client):
        """POST /chat with existing session_id → continues conversation."""
        mock_claude.return_value = "Erste Antwort"
        resp1 = await client.post("/chat", json={"message": "Hallo"})
        session_id = resp1.json()["session_id"]

        mock_claude.return_value = "Zweite Antwort"
        resp2 = await client.post("/chat", json={"message": "Weiter", "session_id": session_id})
        assert resp2.status_code == 200
        assert resp2.json()["session_id"] == session_id
        assert resp2.json()["answer"] == "Zweite Antwort"

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_chat_context_grows(self, mock_claude, client):
        """Each message should include growing conversation history."""
        mock_claude.return_value = "Response"

        # Send 3 messages
        resp1 = await client.post("/chat", json={"message": "Msg 1"})
        sid = resp1.json()["session_id"]

        await client.post("/chat", json={"message": "Msg 2", "session_id": sid})
        await client.post("/chat", json={"message": "Msg 3", "session_id": sid})

        # Check the 3rd call — Claude should receive full history
        last_call_messages = mock_claude.call_args[0][0]
        # Should have: msg1 + resp1 + msg2 + resp2 + msg3 = 5 messages
        assert len(last_call_messages) == 5

    @pytest.mark.asyncio
    async def test_chat_empty_message(self, client):
        """POST /chat with empty message → 400."""
        resp = await client.post("/chat", json={"message": ""})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_whitespace_only(self, client):
        """POST /chat with whitespace → 400."""
        resp = await client.post("/chat", json={"message": "   "})
        assert resp.status_code == 400

    @pytest.mark.asyncio
    async def test_chat_missing_message(self, client):
        """POST /chat without message field → 422."""
        resp = await client.post("/chat", json={})
        assert resp.status_code == 422

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_chat_invalid_session_creates_new(self, mock_claude, client):
        """POST /chat with non-existent session_id → creates new session."""
        mock_claude.return_value = "OK"

        resp = await client.post("/chat", json={
            "message": "Hallo",
            "session_id": "non-existent-uuid"
        })
        assert resp.status_code == 200
        # Should create a new session (different ID)
        assert resp.json()["session_id"] != "non-existent-uuid"


# ═══════════════════════════════════════════════════════════════════════════════
# 5. SESSIONS ENDPOINTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestSessionsEndpoints:

    @pytest.mark.asyncio
    async def test_sessions_empty(self, client):
        """GET /sessions with no data → 200, empty list."""
        resp = await client.get("/sessions")
        assert resp.status_code == 200
        assert resp.json() == []

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_sessions_list_after_chat(self, mock_claude, client):
        """After chatting, GET /sessions should return the session."""
        mock_claude.return_value = "Response"
        chat_resp = await client.post("/chat", json={"message": "Hallo Welt"})
        session_id = chat_resp.json()["session_id"]

        resp = await client.get("/sessions")
        assert resp.status_code == 200
        sessions = resp.json()
        assert len(sessions) >= 1
        assert any(s["id"] == session_id for s in sessions)

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_sessions_schema(self, mock_claude, client):
        """Session response must have: id, title, message_count, created_at, updated_at."""
        mock_claude.return_value = "Response"
        await client.post("/chat", json={"message": "Schema test"})

        resp = await client.get("/sessions")
        session = resp.json()[0]
        assert set(session.keys()) == {"id", "title", "message_count", "created_at", "updated_at"}
        assert session["message_count"] == 2  # user + assistant

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_sessions_title_auto_set(self, mock_claude, client):
        """First user message becomes session title."""
        mock_claude.return_value = "Response"
        await client.post("/chat", json={"message": "Gastro Berlin Trends"})

        resp = await client.get("/sessions")
        session = resp.json()[0]
        assert session["title"] == "Gastro Berlin Trends"  # short enough, no truncation

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_sessions_title_truncation(self, mock_claude, client):
        """Long messages get truncated at 60 chars with ellipsis."""
        mock_claude.return_value = "Response"
        long_msg = "A" * 100
        await client.post("/chat", json={"message": long_msg})

        resp = await client.get("/sessions")
        title = resp.json()[0]["title"]
        assert len(title) <= 60
        assert title.endswith("…")

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_get_session_messages(self, mock_claude, client):
        """GET /sessions/{id}/messages → returns message list."""
        mock_claude.return_value = "Claude antwortet"
        chat_resp = await client.post("/chat", json={"message": "Test Nachricht"})
        session_id = chat_resp.json()["session_id"]

        resp = await client.get(f"/sessions/{session_id}/messages")
        assert resp.status_code == 200
        messages = resp.json()
        assert len(messages) == 2  # user + assistant

        assert messages[0]["role"] == "user"
        assert messages[0]["content"] == "Test Nachricht"
        assert messages[1]["role"] == "assistant"
        assert messages[1]["content"] == "Claude antwortet"

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_messages_schema(self, mock_claude, client):
        """Message response must have: id, role, content, created_at."""
        mock_claude.return_value = "Response"
        chat_resp = await client.post("/chat", json={"message": "Schema"})
        session_id = chat_resp.json()["session_id"]

        resp = await client.get(f"/sessions/{session_id}/messages")
        msg = resp.json()[0]
        assert set(msg.keys()) == {"id", "role", "content", "created_at"}

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_delete_session(self, mock_claude, client):
        """DELETE /sessions/{id} → 200, session gone from list."""
        mock_claude.return_value = "Response"
        chat_resp = await client.post("/chat", json={"message": "Lösch mich"})
        session_id = chat_resp.json()["session_id"]

        # Delete
        del_resp = await client.delete(f"/sessions/{session_id}")
        assert del_resp.status_code == 200
        assert del_resp.json()["deleted"] == session_id

        # Verify gone
        list_resp = await client.get("/sessions")
        assert not any(s["id"] == session_id for s in list_resp.json())

    @pytest.mark.asyncio
    async def test_delete_nonexistent_session(self, client):
        """DELETE /sessions/{bad_id} → 404."""
        resp = await client.delete("/sessions/does-not-exist")
        assert resp.status_code == 404

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_delete_cascades_messages(self, mock_claude, client):
        """Deleting a session should also delete its messages."""
        mock_claude.return_value = "Response"
        chat_resp = await client.post("/chat", json={"message": "Cascade test"})
        session_id = chat_resp.json()["session_id"]

        await client.delete(f"/sessions/{session_id}")

        # Messages for deleted session should be empty/404
        msg_resp = await client.get(f"/sessions/{session_id}/messages")
        assert msg_resp.status_code == 200
        assert msg_resp.json() == []

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_sessions_ordered_by_updated(self, mock_claude, client):
        """GET /sessions should return most recently updated first."""
        mock_claude.return_value = "Response"

        # Create 2 sessions
        r1 = await client.post("/chat", json={"message": "Session 1"})
        sid1 = r1.json()["session_id"]

        r2 = await client.post("/chat", json={"message": "Session 2"})
        sid2 = r2.json()["session_id"]

        resp = await client.get("/sessions")
        sessions = resp.json()
        assert len(sessions) >= 2
        # Most recent should be first
        assert sessions[0]["id"] == sid2


# ═══════════════════════════════════════════════════════════════════════════════
# 6. ERROR HANDLING TESTS
# ═══════════════════════════════════════════════════════════════════════════════

class TestErrorHandling:

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_claude_timeout_returns_504(self, mock_claude, client):
        """Claude timeout → 504 with German error message."""
        from fastapi import HTTPException
        mock_claude.side_effect = HTTPException(status_code=504, detail="Claude-API hat nicht rechtzeitig geantwortet.")

        resp = await client.post("/chat", json={"message": "Timeout test"})
        assert resp.status_code == 504

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_claude_rate_limit_returns_429(self, mock_claude, client):
        """Claude rate limit → 429."""
        from fastapi import HTTPException
        mock_claude.side_effect = HTTPException(status_code=429, detail="Rate limit")

        resp = await client.post("/chat", json={"message": "Rate limit"})
        assert resp.status_code == 429

    @pytest.mark.asyncio
    @patch("app.routers.chat.ask_claude", new_callable=AsyncMock)
    async def test_unexpected_error_returns_500(self, mock_claude, client):
        """Unexpected exception → 500 with detail."""
        mock_claude.side_effect = RuntimeError("Unexpected crash")

        resp = await client.post("/chat", json={"message": "Crash test"})
        assert resp.status_code == 500
        assert "Chat-Fehler" in resp.json()["detail"]

    @pytest.mark.asyncio
    async def test_unknown_route_returns_404(self, client):
        """GET /nonexistent → 404."""
        resp = await client.get("/nonexistent")
        assert resp.status_code in (404, 405)

    @pytest.mark.asyncio
    async def test_wrong_method_search(self, client):
        """GET /search (wrong method) → 405."""
        resp = await client.get("/search")
        assert resp.status_code == 405
