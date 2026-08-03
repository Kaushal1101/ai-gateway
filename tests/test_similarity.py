from unittest.mock import AsyncMock, MagicMock, patch

from gateway.router import OLLAMA_MODEL, OPENAI_MODEL
from gateway.similarity import find_similar


def _make_row(model: str, similarity: float) -> MagicMock:
    row = MagicMock()
    row.chosen_model = model
    row.similarity = similarity
    return row


def _mock_db_session(rows: list) -> MagicMock:
    session = MagicMock()
    session.execute = AsyncMock(return_value=rows)
    session.__aenter__ = AsyncMock(return_value=session)
    session.__aexit__ = AsyncMock(return_value=False)
    return MagicMock(return_value=session)


async def test_find_similar_returns_empty_for_none_vec():
    result = await find_similar(None)
    assert result == []


async def test_find_similar_deduplicates_unanimous_model():
    rows = [
        _make_row(OLLAMA_MODEL, 0.97),
        _make_row(OLLAMA_MODEL, 0.95),
        _make_row(OLLAMA_MODEL, 0.93),
    ]
    with patch("gateway.similarity.AsyncSessionLocal", new=_mock_db_session(rows)):
        result = await find_similar([0.0] * 768)

    assert result == [(OLLAMA_MODEL, 0.97)]


async def test_find_similar_deduplicates_mixed_models():
    rows = [
        _make_row(OLLAMA_MODEL, 0.97),
        _make_row(OLLAMA_MODEL, 0.95),
        _make_row(OPENAI_MODEL, 0.93),
    ]
    with patch("gateway.similarity.AsyncSessionLocal", new=_mock_db_session(rows)):
        result = await find_similar([0.0] * 768)

    assert result == [(OLLAMA_MODEL, 0.97), (OPENAI_MODEL, 0.93)]


async def test_find_similar_returns_empty_when_no_rows():
    with patch("gateway.similarity.AsyncSessionLocal", new=_mock_db_session([])):
        result = await find_similar([0.0] * 768)

    assert result == []
