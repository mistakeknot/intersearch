"""Tests for shared Exa client."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from intersearch.exa import ExaResult, multi_search, search


class TestExaResult:
    def test_creation(self):
        r = ExaResult(title="Test", url="https://example.com")
        assert r.title == "Test"
        assert r.text == ""
        assert r.highlights == []

    def test_defaults(self):
        r = ExaResult(title="T", url="u")
        assert r.score == 0.0
        assert r.author == ""
        assert r.matched_query == ""


class TestSearch:
    @pytest.mark.asyncio
    async def test_no_api_key_returns_empty(self):
        with patch.dict("os.environ", {}, clear=True):
            results = await search("test query", api_key=None)
            assert results == []

    @pytest.mark.asyncio
    async def test_search_with_mock_response(self):
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.json = AsyncMock(
            return_value={
                "results": [
                    {
                        "title": "Test Result",
                        "url": "https://example.com",
                        "text": "Some text",
                        "highlights": ["highlight1"],
                        "score": 0.95,
                        "author": "Author",
                        "publishedDate": "2026-01-01",
                    }
                ]
            }
        )
        mock_response.__aenter__ = AsyncMock(return_value=mock_response)
        mock_response.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post.return_value = mock_response
        mock_session.__aenter__ = AsyncMock(return_value=mock_session)
        mock_session.__aexit__ = AsyncMock(return_value=False)

        with patch(
            "intersearch.exa.aiohttp.ClientSession", return_value=mock_session
        ):
            results = await search("test", api_key="fake-key")
            assert len(results) == 1
            assert results[0].title == "Test Result"
            assert results[0].score == 0.95


class TestMultiSearch:
    @pytest.mark.asyncio
    async def test_deduplicates_by_url(self):
        mock_result = ExaResult(title="Dup", url="https://example.com")
        with patch(
            "intersearch.exa.search", new_callable=AsyncMock
        ) as mock_search:
            mock_search.return_value = [mock_result]
            results = await multi_search(["q1", "q2"], api_key="fake")
            assert len(results) == 1  # Deduplicated
