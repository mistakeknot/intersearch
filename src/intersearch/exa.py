"""Exa semantic search client — shared across interject and interflux."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import aiohttp

logger = logging.getLogger(__name__)

EXA_API = "https://api.exa.ai/search"


@dataclass
class ExaResult:
    """A single Exa search result."""

    title: str
    url: str
    text: str = ""
    highlights: list[str] = field(default_factory=list)
    score: float = 0.0
    author: str = ""
    published_date: str = ""
    matched_query: str = ""


async def search(
    query: str,
    *,
    num_results: int = 10,
    use_autoprompt: bool = True,
    start_date: datetime | None = None,
    text_max_chars: int = 1000,
    highlight_sentences: int = 3,
    api_key: str | None = None,
) -> list[ExaResult]:
    """Run a single Exa semantic search query.

    Returns empty list if no API key is available.
    """
    key = api_key or os.environ.get("EXA_API_KEY")
    if not key:
        logger.warning("No EXA_API_KEY set, skipping search")
        return []

    payload: dict[str, Any] = {
        "query": query,
        "numResults": num_results,
        "useAutoprompt": use_autoprompt,
        "contents": {
            "text": {"maxCharacters": text_max_chars},
            "highlights": {"numSentences": highlight_sentences},
        },
    }
    if start_date:
        payload["startPublishedDate"] = start_date.strftime(
            "%Y-%m-%dT%H:%M:%S.000Z"
        )

    async with aiohttp.ClientSession() as session:
        async with session.post(
            EXA_API,
            json=payload,
            headers={
                "x-api-key": key,
                "Content-Type": "application/json",
            },
        ) as resp:
            if resp.status != 200:
                logger.warning("Exa search failed: HTTP %d", resp.status)
                return []
            data = await resp.json()

    results = []
    for item in data.get("results", []):
        results.append(
            ExaResult(
                title=item.get("title", "") or "",
                url=item.get("url", "") or "",
                text=item.get("text", "") or "",
                highlights=item.get("highlights", []),
                score=item.get("score", 0.0),
                author=item.get("author", "") or "",
                published_date=item.get("publishedDate", "") or "",
                matched_query=query,
            )
        )
    return results


async def multi_search(
    queries: list[str],
    **kwargs: Any,
) -> list[ExaResult]:
    """Run multiple Exa searches and deduplicate by URL."""
    seen_urls: set[str] = set()
    all_results: list[ExaResult] = []

    for query in queries:
        results = await search(query, **kwargs)
        for r in results:
            if r.url not in seen_urls:
                seen_urls.add(r.url)
                all_results.append(r)

    return all_results
