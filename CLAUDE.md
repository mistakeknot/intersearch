# intersearch

Shared embedding and search infrastructure for Interverse. See `AGENTS.md` for philosophy alignment protocol.

## Overview

Infrastructure library, not user-facing. Provides sentence-transformer embeddings and Exa web search as a common dependency for interject and interflux. Installed automatically as a dependency, not standalone.

## Quick Commands

```bash
# Install as dependency
/plugin install intersearch

# Test locally
claude --plugin-dir /root/projects/Interverse/plugins/intersearch
```

## Design Decisions (Do Not Re-Ask)

- Infrastructure library — consumed by interject and interflux as a path dependency
- Sentence-transformer embeddings for semantic search
- Exa web search integration (requires `EXA_API_KEY`)
- Consistent interface so plugins don't reimplement their own embedding pipelines
