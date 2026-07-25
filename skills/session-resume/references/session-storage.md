# Claude Code session storage mechanics

Findings verified empirically on 2026-07-24 (macOS, Claude Code CLI) by creating a
throwaway session, relocating it, and resuming it. Re-verify before relying on any
of it after a major CLI version change.

## Layout

```
~/.claude/projects/
└── <slugified-cwd>/                 e.g. -Users-sma-projects
    ├── <session-id>.jsonl           ← RESUMABLE session (top level only)
    └── <session-id>/                ← that session's subagent transcripts
        └── .../*.jsonl                 (NOT resumable)
```

Slugification is `cwd.replace('/', '-')`. Nothing else is transformed, which is why
a cwd already containing a leading-dash path segment produces a doubled dash
(`/private/tmp/x/-Users-sma-projects/y` → `-private-tmp-x--Users-sma-projects-y`).

Reversing a slug is **ambiguous**, because real directory names contain hyphens:
`-Users-sma-projects-infinite-fun-space` could split many ways. Resolve it against
the filesystem (longest candidate segment first) rather than by string surgery, or
read the cwd recorded inside the transcript.

## Resume is cwd-scoped

`claude --resume <session-id>` resolves the id **only within the project dir for the
current working directory**. From anywhere else it fails with:

```
No conversation found with session ID: <id>
```

The id is valid; the lookup is scoped. This is the single most common reason a
session seems to have vanished. There is no global-by-id resume flag.

Lookup is pure filesystem — no database or index to update. A plain `mv` of the
`.jsonl` into another project dir is sufficient to make it resumable there.

## cwd is recorded per entry, not per session

Every transcript entry carries its own `cwd`. After relocating a session, early
entries retain the old path and new entries record the new one. Consequences:

- The **last** recorded `cwd` is where the session most recently ran.
- The cwd **required to resume** is fixed by the containing directory, which may
  differ from every value recorded inside the file (until it is resumed once).
- A relocated session adopts the new cwd on its next turn rather than fighting it,
  so tool calls and relative paths behave as if it had always lived there.

## Signal-to-noise: most transcripts are not sessions

Per-repo project dirs are frequently *all* spawned agents. Observed counts:
95 files under a jawnomicon dir, 46 under Nartopo, 10 under jawnsight — with **zero**
resumable human-driven sessions among them. The real drivers lived in the umbrella
`~/projects` dir and in `~`.

Auto-spawned transcripts are identifiable by their opening user message. Recurring
openers include:

- `Review this change for security vulnerabilities.` (post-change review hooks)
- `You are the Assayer for flux-melange round N...`
- `Verify these flux-melange findings against reality...`
- `Run a lens-based review probe...` / `Design ONE new distant-domain review lens...`
- `You are implementing...` / `You are executing bead <id>...`
- `Reply with exactly: PROBE-OK` (health probes)

Ranking candidates by message count or transcript size without filtering these
surfaces fan-out workers instead of the thread being looked for.

## Titles mislead; attribute by artifact

A session's title is its first user message, which reflects where the conversation
*started*, not what it became. Real examples:

| Opener | What the session actually did |
|---|---|
| `# Claude Code Doctor Health-check my setup` | Sylveste Rimsky rename + intergraph MCP registration |
| `what's next for cujgel?` | all recent jawnsight grammar/kernel-carry work |
| `do we have a plugin to generate legible context...` | Nartopo pilot-5 scaffolds + kimi-coding backend |

Attribute by grepping for artifacts that only that work would mention — bead ids
(`FLUXrig-7lv`, `Nartopo-uu9`), distinctive commit-message fragments, or unusual
identifiers (`paste_harvest`, `Methgrith`). This succeeds where titles and raw
keyword counts fail.

## Cross-check against git

Transcripts record what was *attempted*; commits record what *survived*. When
reconstructing recent work, read both: `git log --since=<n>` per repo, plus
`git reflog` to distinguish locally-authored commits from ones that arrived via
`pull` (i.e. work done on another machine). A repo whose newest commit is a
fleet-wide docs sweep has not necessarily seen real activity.

## Relationship to session-search

The sibling `session-search` skill queries **content** via cass — semantic and
lexical search over message text, timelines, per-file context, token analytics. It
answers "what did I discuss about X".

It does not surface: which transcript is resumable versus a subagent, the cwd
required to resume, or relocation. Use `session-search` to find *what was
discussed*; use this skill to find *what can be resumed and how*.

## Cautions

- **Size.** Transcripts of 20–45MB compact on the first resumed turn, so the opening
  turns go to re-summarizing. A fresh session seeded from repo state is often faster.
  `--fork-session` resumes under a new id without mutating the original, but still
  sends the full transcript as context — no cost saving.
- **Live sessions.** Never relocate a transcript being actively written; the running
  session holds the old path. Check mtime first.
- **Backups.** `~/.claude` is outside the restic backup set that covers `~/projects`.
  Session history is not backed up; treat relocations as irreversible unless an undo
  script is kept.
- **Indexers.** cass and similar tools store `source_path`; relocating a session
  makes those entries stale until the next reindex.
