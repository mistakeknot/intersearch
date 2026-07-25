---
name: session-resume
description: This skill should be used when the user asks "which session was working on X", "give me the session IDs for these projects", "what sessions have we been working on lately", "I just restarted my computer", "how do I resume the session for X", "why can't claude find my session ID", or asks to move/relocate a session so it resumes from a different directory. Finds resumable Claude Code session IDs and the cwd each requires, filters out subagent transcripts, and relocates sessions between cwd scopes.
user_invocable: true
---

# Session Resume & Forensics

Find the session that can actually be resumed for a given project, report the working
directory required to resume it, and relocate sessions whose cwd scope is wrong.

Distinct from the sibling `session-search` skill, which searches session *content* via
cass. Use `session-search` for "what did I discuss about X"; use this skill for "what
can I resume, and how".

**Announce at start:** "I'm using the session-resume skill to locate your resumable sessions."

## Critical Facts

Two facts drive every workflow here. Both are verified; see
`references/session-storage.md` for evidence and detail.

1. **`claude --resume <id>` is cwd-scoped.** It resolves the id only within the project
   directory matching the current working directory. From anywhere else it reports
   `No conversation found with session ID` even though the id is valid. Always report a
   session id together with the cwd required to resume it — an id alone is not actionable.

2. **Most transcripts are not resumable sessions.** Only files at the top level of
   `~/.claude/projects/<slugified-cwd>/` are sessions. Nested `<session-id>/` directories
   hold that session's subagent transcripts. Per-repo project dirs are often 100%
   subagents with zero resumable sessions — the real driver typically lives in an
   umbrella dir such as `~/projects`, or in `~`.

## Workflow: find the session for a project

Run the finder rather than hand-rolling `jq`/`rg` passes:

```bash
python3 "$CLAUDE_PLUGIN_ROOT/skills/session-resume/scripts/find-session.py" <project-term>
```

Output gives, per candidate: modified time, size, term hits, session-vs-agent
classification, session id, and the resume cwd. Subagent transcripts are filtered by
default (`--all` to include them).

Useful flags:

| Flag | Use |
|---|---|
| `--attribute` | Rank strictly by term count — for bead ids and commit fragments |
| `--days N` | Restrict to recently modified sessions |
| `--list-live` | Sessions written in the last 10 minutes (what is running now) |
| `--json` | Machine-readable output |

When the project term returns nothing convincing, **attribute by artifact instead of
by name**. Session titles are just the first user message and routinely misdescribe
what the session became — jawnsight work sat under `what's next for cujgel?`, and
Sylveste architecture work under a `claude doctor` health-check. Grep for something
only that work would mention:

```bash
python3 .../find-session.py FLUXrig-7lv --attribute      # bead id
python3 .../find-session.py paste_harvest --attribute    # distinctive identifier
```

Then cross-check against git, since transcripts show attempts and commits show what
survived. `git log --since=<n>` per repo, and `git reflog` to tell locally-authored
commits from ones that arrived by `pull` from another machine — recent commits do not
prove recent local sessions.

## Workflow: report findings

Present a table of project → session id → resume cwd, then ready-to-paste commands:

```bash
cd <resume cwd> && claude --resume <session-id>
```

Flag two things whenever they apply:

- **Sessions over ~20MB** compact on the first resumed turn, spending opening turns on
  re-summarizing. Say so and offer a fresh session seeded from repo state as the
  faster path. `--fork-session` preserves the original but still sends full context.
- **Sessions written within the last few minutes** are live. Resuming attaches to
  active work; note it instead of presenting it as a cold start.

## Workflow: relocate a session

To make a session resumable from a different directory:

```bash
bash "$CLAUDE_PLUGIN_ROOT/skills/session-resume/scripts/move-session.sh" <session-id> <target-cwd> [--dry-run]
```

The script moves the transcript and its companion subagent directory, refuses to touch
a session written within the last 120 seconds, refuses on id collision, and appends a
reversal line to `~/.claude/session-move-undo-<date>.sh`.

Before moving, confirm the session is idle and state that history under `~/.claude` is
outside the restic backup set covering `~/projects` — relocations are recoverable only
via the undo script.

Leave sessions scoped to a specific repo alone unless asked. A session at
`~/projects/<repo>` picks up that repo's `AGENTS.md`/`CLAUDE.md`; hoisting it to an
umbrella dir strips that context. Relocation is for sessions in genuinely wrong scopes,
such as project work stranded under `~`.

## Verifying relocation

Do not verify by resuming a large real session — that sends the entire transcript as
context and appends a junk turn. Verify the mechanism once on a throwaway:

```bash
mkdir -p /tmp/rt && cd /tmp/rt
U=$(python3 -c "import uuid;print(uuid.uuid4())")
claude -p --session-id "$U" "Reply with exactly: OK"
mv ~/.claude/projects/-tmp-rt/"$U".jsonl ~/.claude/projects/<target-slug>/
cd <target-cwd> && claude -p --resume "$U" "Reply with exactly: OK"
```

For real sessions, verify file placement only.

## Shell caution

Use `bash` for id loops. Under `zsh`, `for id in $IDS` with a space-separated string
does not word-split — the loop runs once with the ids concatenated and `mv` fails with
a confusing "No such file or directory" naming the joined path. Use a literal list or
an array.

## Additional Resources

- **`references/session-storage.md`** — storage layout, slugification and why reversing
  it is ambiguous, per-entry cwd semantics, the subagent-opener catalogue used for
  filtering, title-misattribution examples, and cautions.
- **`scripts/find-session.py`** — locate resumable sessions and their resume cwd.
- **`scripts/move-session.sh`** — relocate a session between cwd scopes, with undo.
