#!/usr/bin/env python3
"""Locate the resumable Claude Code session for a project, plus the cwd needed to resume it.

Claude Code stores transcripts at ~/.claude/projects/<slugified-cwd>/<session-id>.jsonl.
Only files at the TOP LEVEL of a project dir are resumable sessions; nested
<session-id>/ dirs hold that session's subagent transcripts, which are not resumable.

Usage:
    find-session.py <term> [<term> ...] [options]

    find-session.py jawnomicon
    find-session.py FLUXrig-7lv --attribute      # attribute by bead id / commit string
    find-session.py nartopo --days 14 --json
    find-session.py --list-live                  # sessions written in the last 10 min

Options:
    --days N        Only consider sessions modified in the last N days (default: all)
    --limit N       Rows to print (default: 8)
    --all           Include subagent-prompt sessions (default: filtered out)
    --attribute     Rank strictly by term count; use for bead ids / commit strings
    --json          Emit JSON instead of a table
    --list-live     Show sessions modified within 10 minutes and exit
    --root PATH     Projects root (default: ~/.claude/projects)
"""

import argparse
import json
import os
import sys
import time

# Opening lines that mark a transcript as a spawned agent rather than a session
# a human drove. These dominate by volume: a repo dir can hold 95 files and
# zero resumable sessions.
AGENT_PREFIXES = (
    "you are ", "you're the", "you design", "you previously flagged",
    "verify these", "run a lens", "run a focused", "design one",
    "review this change for security", "read-only recon", "read and follow exactly",
    "i need to determine", "analyze the", "implement two",
    "base directory for this skill", "reply with exactly",
)


def slugify(path):
    """Claude Code's cwd -> project-dir-name transform: '/' becomes '-'."""
    return path.replace("/", "-")


def unslug(slug):
    """Reconstruct a cwd from a project dir name.

    Ambiguous in general, because real path segments may contain '-'
    ('infinite-fun-space' slugifies to the same shape as three segments).
    Resolved by testing the filesystem, longest candidate segment first.
    Returns None when no existing path matches.
    """
    parts = slug.lstrip("-").split("-")
    path = "/"
    i = 0
    while i < len(parts):
        for j in range(len(parts), i, -1):
            cand = os.path.join(path, "-".join(parts[i:j]))
            if os.path.isdir(cand):
                path, i = cand, j
                break
        else:
            return None
    return path


def count_subagents(session_dir):
    """Count a session's subagent transcripts. They sit several levels deep
    inside <session-id>/, not directly in it."""
    if not os.path.isdir(session_dir):
        return 0
    n = 0
    for _, _, files in os.walk(session_dir):
        n += sum(1 for f in files if f.endswith(".jsonl"))
    return n


def read_meta(path, max_lines=600):
    """Return (first_human_text, recorded_cwd) without reading a whole
    transcript. Transcripts reach tens of MB; the opener is near the top.

    cwd is recorded per ENTRY, not per session, so a relocated session shows its
    old cwd in early entries and the new one in later entries. Not every entry
    carries one, so scanning continues until both values are found.
    """
    first_text, last_cwd = "", None
    try:
        with open(path, errors="replace") as fh:
            for i, line in enumerate(fh):
                if i > max_lines and first_text and last_cwd:
                    break
                try:
                    d = json.loads(line)
                except Exception:
                    continue
                if d.get("cwd"):
                    last_cwd = d["cwd"]
                if first_text or d.get("type") != "user":
                    continue
                msg = d.get("message")
                if not isinstance(msg, dict):
                    continue
                c = msg.get("content")
                if isinstance(c, str):
                    t = c
                elif isinstance(c, list):
                    t = " ".join(x.get("text", "") for x in c if isinstance(x, dict))
                else:
                    continue
                t = " ".join(t.split())
                if not t or t.startswith("<") or "system-reminder" in t[:60]:
                    continue
                first_text = t
    except OSError:
        pass
    return first_text, last_cwd


def resume_cwd(jsonl_path, recorded_cwd):
    """The cwd required to resume, which is fixed by the containing dir --
    NOT by what the transcript recorded (a relocated session records a cwd it
    can no longer be resumed from).

    Returns (cwd, verified). Verified means the value round-trips back to the
    directory name, so it is certain rather than a best guess.
    """
    slug = os.path.basename(os.path.dirname(jsonl_path))
    if recorded_cwd and slugify(recorded_cwd) == slug:
        return recorded_cwd, True
    resolved = unslug(slug)
    # A filesystem-resolved path that slugifies back to this exact directory is
    # just as certain as a recorded one.
    return resolved, bool(resolved) and slugify(resolved) == slug


def scan(root, terms, days, include_agents, attribute):
    cutoff = time.time() - days * 86400 if days else 0
    rows = []
    for slug in os.listdir(root):
        d = os.path.join(root, slug)
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            if not name.endswith(".jsonl"):
                continue
            p = os.path.join(d, name)
            try:
                st = os.stat(p)
            except OSError:
                continue
            if st.st_mtime < cutoff or st.st_size == 0:
                continue
            if terms:
                try:
                    with open(p, errors="replace") as fh:
                        blob = fh.read().lower()
                except OSError:
                    continue
                hits = sum(blob.count(t.lower()) for t in terms)
                if not hits:
                    continue
            else:
                hits = 0
            text, rec_cwd = read_meta(p)
            is_agent = text.lower().startswith(AGENT_PREFIXES)
            if is_agent and not include_agents:
                continue
            cwd, exact = resume_cwd(p, rec_cwd)
            sid = name[:-6]
            sub = os.path.join(d, sid)
            rows.append({
                "session_id": sid,
                "resume_cwd": cwd,
                "cwd_exact": exact,
                "modified": time.strftime("%Y-%m-%d %H:%M", time.localtime(st.st_mtime)),
                "mtime": st.st_mtime,
                "size_mb": round(st.st_size / 1048576, 1),
                "hits": hits,
                # Subagent transcripts nest several levels below the session dir,
                # so this needs a walk rather than a listdir.
                "subagent_files": count_subagents(sub),
                "kind": "agent" if is_agent else "session",
                "opener": text[:150],
            })
    # Term count identifies the thread; recency picks the live head of it.
    rows.sort(key=lambda r: (-r["hits"], -r["mtime"]) if attribute else (-r["mtime"],))
    return rows


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("terms", nargs="*")
    ap.add_argument("--days", type=float, default=0)
    ap.add_argument("--limit", type=int, default=8)
    ap.add_argument("--all", action="store_true")
    ap.add_argument("--attribute", action="store_true")
    ap.add_argument("--json", action="store_true")
    ap.add_argument("--list-live", action="store_true")
    ap.add_argument("--root", default=os.path.expanduser("~/.claude/projects"))
    a = ap.parse_args()

    if not os.path.isdir(a.root):
        sys.exit(f"projects root not found: {a.root}")

    if a.list_live:
        rows = [r for r in scan(a.root, [], 0.02, True, False)]
        a.limit = max(a.limit, len(rows))
    else:
        if not a.terms:
            sys.exit("supply at least one search term, or use --list-live")
        rows = scan(a.root, a.terms, a.days, a.all, a.attribute or bool(a.terms))

    rows = rows[: a.limit]
    if a.json:
        print(json.dumps(rows, indent=2))
        return
    if not rows:
        print("no matching sessions")
        return

    print(f"{'modified':<17}{'size':>7}  {'hits':>6}  {'kind':<8}{'session id':<38}resume from")
    for r in rows:
        cwd = r["resume_cwd"] or "UNRESOLVED"
        flag = "" if r["cwd_exact"] else "  (unverified)"
        print(f"{r['modified']:<17}{r['size_mb']:>5}MB  {r['hits']:>6}  "
              f"{r['kind']:<8}{r['session_id']:<38}{cwd}{flag}")
        print(f"{'':19}sub:{r['subagent_files']:<4} {r['opener'][:110]}")
    print("\nresume:  cd <resume from> && claude --resume <session id>")
    print("large transcripts compact on first turn; --fork-session leaves the original intact")


if __name__ == "__main__":
    main()
