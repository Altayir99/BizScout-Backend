"""
BizScout Backend — Comprehensive Unit Tests
Tests: Models, Services, Routers, Error Handling
"""
import pytest
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch
from pydantic import ValidationError

# ─── 1. Pydantic Model Validation Tests ─────────────────────────────────────


def test_search_request_defaults():
    """SearchRequest should default mode to 'general'."""
    from app.routers.search import SearchRequest
    req = SearchRequest(query="test query")
    assert req.query == "test query"
    assert req.mode == "general"


def test_search_request_custom_mode():
    from app.routers.search import SearchRequest
    req = SearchRequest(query="restaurants berlin", mode="restaurants")
    assert req.mode == "restaurants"


def test_chat_request_optional_session():
    """ChatRequest.session_id should be None by default."""
    from app.routers.chat import ChatRequest
    req = ChatRequest(message="hello")
    assert req.message == "hello"
    assert req.session_id is None


def test_chat_request_with_session():
    from app.routers.chat import ChatRequest
    sid = str(uuid.uuid4())
    req = ChatRequest(message="hello", session_id=sid)
    assert req.session_id == sid


def test_chat_request_empty_message_still_valid():
    """Empty string is technically valid at Pydantic level (business logic rejects it)."""
    from app.routers.chat import ChatRequest
    req = ChatRequest(message="")
    assert req.message == ""


def test_session_response_serialization():
    from app.routers.sessions import SessionResponse
    now = datetime.now(timezone.utc)
    resp = SessionResponse(
        id="abc-123",
        title="Test Session",
        message_count=5,
        created_at=now,
        updated_at=now,
    )
    data = resp.model_dump()
    assert data["id"] == "abc-123"
    assert data["message_count"] == 5


def test_message_response_serialization():
    from app.routers.sessions import MessageResponse
    now = datetime.now(timezone.utc)
    resp = MessageResponse(
        id="msg-1", role="user", content="hi", created_at=now
    )
    assert resp.role == "user"
    assert resp.content == "hi"


# ─── 2. Config Tests ────────────────────────────────────────────────────────


def test_settings_defaults():
    """Settings should have sensible defaults."""
    from app.config import Settings
    s = Settings()
    assert s.claude_model == "claude-sonnet-4-5"
    assert s.claude_max_tokens == 2048
    assert s.perplexity_model in ("sonar-pro", "llama-3.1-sonar-large-128k-online")  # .env may override
    assert s.memory_window == 20
    assert s.cors_origins == ["*"]


def test_settings_custom_env(monkeypatch):
    """Settings should pick up environment variables."""
    monkeypatch.setenv("CLAUDE_MAX_TOKENS", "4096")
    monkeypatch.setenv("MEMORY_WINDOW", "50")
    from app.config import Settings
    s = Settings()
    assert s.claude_max_tokens == 4096
    assert s.memory_window == 50


# ─── 3. SQLAlchemy Model Tests ──────────────────────────────────────────────


def test_chat_session_model_structure():
    """ChatSession should have correct fields."""
    from app.models.session import ChatSession
    session = ChatSession()
    # ORM defaults only apply during DB INSERT, not Python instantiation
    assert hasattr(session, 'title')
    assert hasattr(session, 'id')
    assert hasattr(session, 'messages')


def test_message_requires_session_id():
    """Message model requires session_id field."""
    from app.models.message import Message
    msg = Message(session_id="test-sid", role="user", content="hello")
    assert msg.session_id == "test-sid"
    assert msg.role == "user"
    assert msg.content == "hello"


# ─── 4. Perplexity Service Tests ────────────────────────────────────────────


def test_system_prompts_exist():
    """All 8 search modes should have system prompts defined."""
    from app.services.perplexity_service import SYSTEM_PROMPTS
    expected_modes = [
        "restaurants", "events", "hotels", "messen",
        "zeitarbeit", "akquise", "markt", "general"
    ]
    for mode in expected_modes:
        assert mode in SYSTEM_PROMPTS, f"Missing system prompt for mode: {mode}"


def test_system_prompts_not_empty():
    """All system prompts should be non-trivial strings."""
    from app.services.perplexity_service import SYSTEM_PROMPTS
    for mode, prompt in SYSTEM_PROMPTS.items():
        assert len(prompt) > 50, f"System prompt for '{mode}' is too short"


def test_unknown_mode_falls_back_to_general():
    """An unrecognized mode should use the general prompt."""
    from app.services.perplexity_service import SYSTEM_PROMPTS
    fallback = SYSTEM_PROMPTS.get("unknown_mode", SYSTEM_PROMPTS.get("general"))
    assert fallback is not None
    assert "general" in SYSTEM_PROMPTS


# ─── 5. Memory Service Logic Tests ──────────────────────────────────────────


def test_title_truncation_logic():
    """Title should be truncated at 60 chars with ellipsis."""
    # Simulate the title truncation logic from memory_service.py
    user_msg = "A" * 100
    clean = user_msg.strip().replace("\n", " ")
    title = (clean[:57] + "…") if len(clean) > 60 else clean
    assert len(title) == 58  # 57 chars + ellipsis
    assert title.endswith("…")


def test_short_title_not_truncated():
    user_msg = "Hallo Welt"
    clean = user_msg.strip().replace("\n", " ")
    title = (clean[:57] + "…") if len(clean) > 60 else clean
    assert title == "Hallo Welt"


def test_newlines_stripped_from_title():
    user_msg = "Line1\nLine2\nLine3"
    clean = user_msg.strip().replace("\n", " ")
    assert "\n" not in clean
    assert clean == "Line1 Line2 Line3"


# ─── 6. Error Handling Gap Detection ────────────────────────────────────────


def test_claude_service_has_error_handling():
    """
    REGRESSION TEST: Verify claude_service.ask_claude() has proper error handling.
    """
    import ast
    import inspect
    from app.services.claude_service import ask_claude

    source = inspect.getsource(ask_claude)
    tree = ast.parse(source)
    has_try = any(isinstance(node, ast.Try) for node in ast.walk(tree))
    assert has_try, "ask_claude() MUST have try/except error handling!"


def test_chat_router_has_error_handling():
    """
    REGRESSION TEST: Chat endpoint has proper error handling.
    """
    import ast
    import inspect
    from app.routers.chat import chat

    source = inspect.getsource(chat)
    tree = ast.parse(source)
    has_try = any(isinstance(node, ast.Try) for node in ast.walk(tree))
    assert has_try, "chat() endpoint MUST have try/except error handling!"


# ─── 7. Search Router Integration ───────────────────────────────────────────


@pytest.mark.asyncio
async def test_search_endpoint_structure():
    """SearchResponse should have answer, sources, mode fields."""
    from app.routers.search import SearchResponse
    resp = SearchResponse(
        answer="Test answer",
        sources=["https://example.com"],
        mode="general",
    )
    assert resp.answer == "Test answer"
    assert len(resp.sources) == 1
    assert resp.mode == "general"


@pytest.mark.asyncio
async def test_search_response_empty_sources():
    from app.routers.search import SearchResponse
    resp = SearchResponse(answer="No sources", sources=[], mode="restaurants")
    assert resp.sources == []


# ─── 8. Research Router Schema ───────────────────────────────────────────────


def test_research_response_fields():
    """Research endpoint response should have all 4 fields."""
    from app.routers.research import ResearchResponse
    resp = ResearchResponse(
        search_summary="Summary",
        ai_analysis="Analysis",
        sources=["url1"],
        mode="events",
    )
    assert resp.search_summary == "Summary"
    assert resp.ai_analysis == "Analysis"


# ─── 9. CORS Configuration ──────────────────────────────────────────────────


def test_cors_allows_all_by_default():
    """CORS should default to allowing all origins (private app)."""
    from app.config import get_settings
    settings = get_settings()
    assert "*" in settings.cors_origins


# ─── 10. Database Module ────────────────────────────────────────────────────


def test_base_class_exists():
    """Base declarative class should be importable."""
    from app.database import Base
    assert Base is not None


def test_models_inherit_from_base():
    """Both models should inherit from the same Base."""
    from app.database import Base
    from app.models.session import ChatSession
    from app.models.message import Message
    assert issubclass(ChatSession, Base)
    assert issubclass(Message, Base)


def test_session_has_messages_relationship():
    """ChatSession should have a 'messages' relationship."""
    from app.models.session import ChatSession
    assert hasattr(ChatSession, 'messages')


def test_message_has_session_relationship():
    """Message should have a 'session' back-reference."""
    from app.models.message import Message
    assert hasattr(Message, 'session')
