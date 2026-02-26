# intersearch

Shared embedding and search infrastructure for Interverse.

## Overview

Infrastructure library + MCP server. Provides nomic-embed-text-v1.5 (768d) embeddings with persistent SQLite vector storage, and Exa web search. Consumed by interject, interflux, intercache, and tldr-swinton.

## MCP Server

Python MCP server at `src/intersearch/server.py`. Run with `uv run intersearch-mcp`.

## Key Files

- `src/intersearch/embeddings.py` — EmbeddingClient (nomic-embed-text-v1.5, 768d; legacy MiniLM supported)
- `src/intersearch/store.py` — EmbeddingStore (per-project SQLite, WAL mode, incremental indexing)
- `src/intersearch/server.py` — MCP server (embedding_index, embedding_query)
- `src/intersearch/exa.py` — Exa async web search client

## MCP Tools

| Tool | Purpose |
|------|---------|
| `embedding_index` | Index files for semantic search (incremental, SHA256-based dedup) |
| `embedding_query` | Semantic search across indexed files (cosine similarity ranking) |

## Storage

Per-project embeddings stored at `~/.intersearch/index/<project-hash>/embeddings.db`.

## Quick Commands

```bash
# Test locally
uv run --directory . intersearch-mcp

# Run tests
uv run pytest tests/ -v
```

## Design Decisions (Do Not Re-Ask)

- Default model: nomic-ai/nomic-embed-text-v1.5 (768d) — upgraded from all-MiniLM-L6-v2
- Legacy model still supported via `EmbeddingClient(model_name="all-MiniLM-L6-v2")`
- Embedding persistence replaces intercache's embedding tools (2026-02-25)
- Storage at `~/.intersearch/` (independent of intercache)
- Exa web search integration (requires `EXA_API_KEY`)
