# intersearch — Vision and Philosophy

**Version:** 0.1.0
**Last updated:** 2026-02-28

## What intersearch Is

intersearch is the shared embedding and semantic search infrastructure for the Interverse ecosystem. It provides a single, persistent vector store backed by SQLite and nomic-embed-text-v1.5 (768-dimensional embeddings), exposed through two MCP tools: `embedding_index` and `embedding_query`. It also bundles an async Exa web search client. Any plugin that needs to find things semantically — across files, memory, or the web — reaches for intersearch rather than reimplementing its own embedding stack.

The design is deliberately narrow. intersearch does not interpret results, rank by intent, or decide what to search. It encodes content into durable vectors and retrieves the closest ones by cosine similarity. That constraint is the point: consumers (Interject, Interflux, Intercache, tldr-swinton) own the policy; intersearch owns the mechanism.

## Why This Exists

Before intersearch, every plugin that needed embeddings embedded its own embedding logic — intercache had its own embedding tools, interject had its own retrieval path. That duplication meant diverging model versions, inconsistent storage formats, and no shared index across tools. intersearch consolidates that into a single canonical source. Composition over capability: one well-tested infrastructure layer that many consumers compose, rather than four parallel implementations each half-working.

## Design Principles

1. **Mechanism, not policy.** intersearch indexes and retrieves; it does not decide what is relevant. Consumers apply business logic on top of ranked results.
2. **Durable, content-addressed storage.** Each embedding is keyed by file path and SHA256. Unchanged content is never re-embedded. Model version changes invalidate and rebuild automatically — no manual cache management.
3. **Per-project isolation.** Each project gets its own SQLite database at `~/.intersearch/index/<project-hash>/embeddings.db`. Indices don't bleed across projects; consumers don't share state they didn't opt into.
4. **Incremental by default.** The indexing path is SHA256-gated: only changed content triggers new embedding calls. Large codebases stay fast after the initial pass.
5. **Fail-open on external dependencies.** Exa web search degrades gracefully when `EXA_API_KEY` is absent — returns empty results rather than erroring. Local embedding is never gated on an external API.

## Scope

**What intersearch does:**
- Embeds file content using nomic-embed-text-v1.5 (768d) via sentence-transformers
- Persists vectors in per-project SQLite with WAL mode for concurrent access
- Answers `embedding_query` calls with top-K cosine similarity results
- Provides async Exa web search with deduplication across multi-query fans

**What intersearch does not do:**
- Apply relevance filtering, re-ranking, or intent modeling
- Own any data lifecycle decisions (retention, eviction, archiving)
- Provide a UI or direct CLI search interface
- Replace full-text search — it is semantic, not keyword-based

## Direction

- Expose stale path detection as a first-class MCP tool so consumers can drive incremental re-index without polling the full index.
- Support batched embedding calls to reduce model-load overhead when indexing many files in a single session.
- Add a lightweight index-stats tool (count, model version, last-updated) to give consumers and agents observability into the current index state without querying the database directly.
