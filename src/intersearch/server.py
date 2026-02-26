"""MCP server — embedding_index and embedding_query tools.

Provides persistent semantic search for project files via the intersearch
embedding store. Replaces the embedding tools previously hosted in intercache.
"""

from __future__ import annotations

import hashlib
import json
import logging
import sys
from pathlib import Path

from mcp.server import Server
from mcp.server.stdio import stdio_server
from mcp.types import TextContent, Tool

from .store import EmbeddingStore

logger = logging.getLogger(__name__)

app = Server("intersearch")

# Cache embedding stores per project root
_stores: dict[str, EmbeddingStore] = {}


def _get_store(project_root: str) -> EmbeddingStore:
    if project_root not in _stores:
        _stores[project_root] = EmbeddingStore(project_root)
    return _stores[project_root]


def _ok(data: dict) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps(data, indent=2))]


def _err(msg: str) -> list[TextContent]:
    return [TextContent(type="text", text=json.dumps({"error": msg}))]


def _sha256_file(path: Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(8192), b""):
            h.update(chunk)
    return h.hexdigest()


@app.list_tools()
async def list_tools() -> list[Tool]:
    return [
        Tool(
            name="embedding_index",
            description=(
                "Index files for semantic search. Embeds file content using "
                "nomic-embed-text-v1.5 (768d). Incremental — only re-embeds changed files."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_root": {
                        "type": "string",
                        "description": "Absolute path to project root",
                    },
                    "paths": {
                        "type": "array",
                        "items": {"type": "string"},
                        "description": "Specific file paths to index (relative to project root). If omitted, indexes all text files.",
                    },
                },
                "required": ["project_root"],
            },
        ),
        Tool(
            name="embedding_query",
            description=(
                "Semantic search across indexed files. Returns top-K files ranked "
                "by cosine similarity to the query."
            ),
            inputSchema={
                "type": "object",
                "properties": {
                    "project_root": {
                        "type": "string",
                        "description": "Absolute path to project root",
                    },
                    "query": {
                        "type": "string",
                        "description": "Natural language search query",
                    },
                    "top_k": {
                        "type": "integer",
                        "description": "Number of results to return (default 10)",
                        "default": 10,
                    },
                },
                "required": ["project_root", "query"],
            },
        ),
    ]


# Text file extensions we index
_TEXT_EXTENSIONS = {
    ".py", ".js", ".ts", ".jsx", ".tsx", ".go", ".rs", ".java", ".c", ".cpp",
    ".h", ".hpp", ".cs", ".rb", ".php", ".swift", ".kt", ".scala", ".lua",
    ".sh", ".bash", ".zsh", ".fish", ".ps1", ".bat",
    ".md", ".txt", ".rst", ".adoc", ".org",
    ".json", ".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf",
    ".html", ".css", ".scss", ".less", ".svg",
    ".sql", ".graphql", ".proto",
    ".dockerfile", ".makefile",
}

_SKIP_DIRS = {
    ".git", "node_modules", "__pycache__", ".venv", "venv", "dist", "build",
    ".tox", ".mypy_cache", ".pytest_cache", ".next", "target", "vendor",
}

_MAX_FILE_SIZE = 256 * 1024  # 256KB


def _discover_text_files(project_root: Path) -> list[Path]:
    """Walk project and find indexable text files."""
    files = []
    for p in project_root.rglob("*"):
        if any(part in _SKIP_DIRS for part in p.parts):
            continue
        if p.is_file() and p.suffix.lower() in _TEXT_EXTENSIONS:
            if p.stat().st_size <= _MAX_FILE_SIZE:
                files.append(p)
    return files


@app.call_tool()
async def call_tool(name: str, arguments: dict) -> list[TextContent]:
    try:
        if name == "embedding_index":
            return await _handle_index(arguments)
        elif name == "embedding_query":
            return await _handle_query(arguments)
        else:
            return _err(f"Unknown tool: {name}")
    except Exception as e:
        logger.exception("Tool %s failed", name)
        return _err(str(e))


async def _handle_index(args: dict) -> list[TextContent]:
    project_root = args["project_root"]
    store = _get_store(project_root)
    root = Path(project_root)

    paths = args.get("paths")
    if paths:
        files = [root / p for p in paths]
    else:
        files = _discover_text_files(root)

    indexed = 0
    skipped = 0
    errors = 0

    for fpath in files:
        try:
            if not fpath.exists() or not fpath.is_file():
                errors += 1
                continue

            sha = _sha256_file(fpath)
            content = fpath.read_text(encoding="utf-8", errors="replace")
            rel = str(fpath.relative_to(root))

            if store.index_file(rel, content, sha):
                indexed += 1
            else:
                skipped += 1
        except Exception:
            errors += 1

    return _ok({"indexed": indexed, "skipped": skipped, "errors": errors})


async def _handle_query(args: dict) -> list[TextContent]:
    project_root = args["project_root"]
    query = args["query"]
    top_k = args.get("top_k", 10)

    store = _get_store(project_root)
    results = store.query(query, top_k=top_k)

    return _ok({"query": query, "results": results, "total_indexed": store.count()})


async def main():
    async with stdio_server() as (read_stream, write_stream):
        await app.run(read_stream, write_stream, app.create_initialization_options())


def cli_main():
    """Entry point for console_scripts."""
    import asyncio
    asyncio.run(main())


if __name__ == "__main__":
    cli_main()
