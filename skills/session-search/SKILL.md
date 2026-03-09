---
name: session-search
description: Search past agent sessions, view timelines, find sessions by file, export transcripts, and analyze token/tool/model usage. Delegates to cass (Rust-native, sub-60ms, 15 agent providers). Use when the user asks "what did I work on?", "find sessions about X", "show session stats", "what sessions touched this file?", "export this session", or "show token analytics".
user_invocable: true
---

# Session Search & Analytics

Search and analyze past coding agent sessions across all providers (Claude Code, Codex, Gemini, Cursor, etc.). Powered by [cass](https://github.com/Dicklesworthstone/coding_agent_session_search).

**Requires:** cass >= 0.2.0 (`~/.local/bin/cass`)

**Announce at start:** "I'm using the session-search skill to query your session history."

## Step 0: Pre-flight Check

Verify cass is installed:

```bash
if ! command -v cass > /dev/null 2>&1; then
    echo "cass not installed. Install: curl -fsSL \"https://raw.githubusercontent.com/Dicklesworthstone/coding_agent_session_search/main/install.sh\" | bash"
fi
CASS_VERSION=$(cass --version 2>/dev/null | grep -oP '\d+\.\d+\.\d+' | head -1)
echo "cass version: $CASS_VERSION"
```

If cass is missing, tell the user to install it and stop. If version is below 0.2.0, warn but continue.

## Step 1: Ensure Index is Fresh

```bash
STALE=$(cass health --json 2>/dev/null | python3 -c "import sys,json; h=json.load(sys.stdin); print(h['state']['index']['stale'])" 2>/dev/null || echo "True")
if [ "$STALE" = "True" ] || [ "$STALE" = "true" ]; then
    cass index --full 2>/dev/null
fi
```

## Step 2: Route by Intent

### "Find sessions about X" / "Search for X"
```bash
cass search "<query>" --robot --limit 10 --mode hybrid
```
Modes: `hybrid` (default, best), `lexical` (keyword-only BM25), `semantic` (embedding similarity).
Filters: `--workspace <path>`, `--agent <slug>`, `--since <date>`, `--until <date>`.

### "What did I work on [this week/recently]?" / "Show timeline"
```bash
cass timeline --today --json
cass timeline --since 7d --json --group-by day
cass timeline --since 2026-03-01 --until 2026-03-07 --json
```
Filters: `--agent <slug>`, `--source local|remote`.

### "What sessions touched this file?" / "Who worked on X?"
```bash
cass context <path/to/file> --json --limit 5
```
Returns sessions that reference the given source path.

### "Export this session" / "Save session transcript"
```bash
cass export <session_file_path> --format markdown -o <output_path>
cass export <session_file_path> --format json -o <output_path>
```
Formats: `markdown`, `text`, `json`, `html`. Use `--include-tools` for tool call details.

### "Show token analytics" / "How many tokens this week?"
```bash
cass analytics tokens --days 7 --json
cass analytics tokens --workspace /path/to/project --json --group-by day
```
Also available: `cass analytics tools --json`, `cass analytics models --json`.

### "Show session stats"
```bash
cass stats --json
```

## Step 3: Present Results

Format output as a readable table or summary. Highlight:
- Number of sessions/messages found
- Project distribution (for stats/timeline)
- Key message excerpts (for search results)
- File relationships (for context results)
- Token breakdowns by agent/model (for analytics)

## Dependencies

- **cass** >= 0.2.0 — session search engine. Install: `curl -fsSL "https://raw.githubusercontent.com/Dicklesworthstone/coding_agent_session_search/main/install.sh" | bash`
- Index location: `~/.local/share/coding-agent-search/`
