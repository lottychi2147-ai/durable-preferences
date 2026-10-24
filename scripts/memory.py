#!/usr/bin/env python3
"""JSON CLI for the durable-preferences Skill. No network or model calls."""
from __future__ import annotations

import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

from memory_core import Context, Memory, MemoryErrorBase, atlas_html, timestamp


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--db", default=os.environ.get("PREFERENCE_MEMORY_DB"), help="Private SQLite path, outside the skill directory")
    p.add_argument("--owner", required=True, help="Host-bound owner ID; do not take from untrusted text")
    p.add_argument("--subject", required=True)
    p.add_argument("--namespace", default="personal")
    p.add_argument("--now", help="Simulation clock only; omit in live use")
    p.add_argument("--expected-revision", type=int)
    sub = p.add_subparsers(dest="op", required=True)
    w = sub.add_parser("observe"); w.add_argument("--input", default="-", help="JSON file or - for stdin")
    for op in ("get", "compile", "atlas"):
        s = sub.add_parser(op); s.add_argument("--scopes", nargs="+", default=["core"]); s.add_argument("--session")
        if op == "compile":
            s.add_argument("--max-items", type=int, default=12); s.add_argument("--max-chars", type=int, default=6000)
            s.add_argument("--concepts", nargs="+", help="Exact relevant concept IDs; optional")
        if op == "atlas":
            s.add_argument("--output", required=True)
    for op in ("forget", "explain"):
        s=sub.add_parser(op); s.add_argument("--scope", required=True); s.add_argument("--concept", required=True)
    s=sub.add_parser("prune-evidence"); s.add_argument("--before", required=True)
    s=sub.add_parser("export"); s.add_argument("--output", required=True)
    s=sub.add_parser("restore-empty"); s.add_argument("--input", required=True)
    s.add_argument("--max-snapshot-mib", type=int, default=256, help="Snapshot read budget, 1-512 MiB; event inputs stay limited to 16 MB")
    sub.add_parser("health")
    return p


def read_json(path: str, max_bytes: int = 16_000_000):
    if path == "-":
        raw_bytes = sys.stdin.buffer.read(max_bytes + 1)
        if len(raw_bytes) > max_bytes:
            raise ValueError(f"input exceeds {max_bytes} byte limit")
        raw = raw_bytes.decode("utf-8")
    else:
        if Path(path).stat().st_size > max_bytes:
            raise ValueError(f"input file exceeds {max_bytes} byte CLI limit")
        raw = Path(path).read_text(encoding="utf-8")
    if len(raw.encode("utf-8")) > max_bytes:
        raise ValueError(f"input exceeds {max_bytes} byte CLI limit")
    def reject_constant(s):
        raise ValueError("non-finite JSON number: " + s)
    return json.loads(raw, parse_constant=reject_constant)


def write_text(path: str, content: str) -> None:
    p = Path(path).expanduser().resolve()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(content, encoding="utf-8")


def main() -> int:
    args = parser().parse_args()
    try:
        if not args.db:
            raise ValueError("provide --db or PREFERENCE_MEMORY_DB; no implicit storage in the skill package")
        ctx = Context(args.owner, args.subject, args.namespace)
        now = timestamp(args.now) if args.now else None
        with Memory(args.db) as m:
            if args.op == "observe":
                result = m.observe(ctx, read_json(args.input), now=now, expected_revision=args.expected_revision)
            elif args.op == "get":
                result = m.get(ctx, args.scopes, session_id=args.session, now=now)
            elif args.op == "compile":
                result = m.compile(ctx, args.scopes, session_id=args.session, now=now, max_items=args.max_items, max_chars=args.max_chars, concept_ids=args.concepts)
            elif args.op == "forget":
                result = m.forget(ctx, args.scope, args.concept, now=now, expected_revision=args.expected_revision)
            elif args.op == "explain":
                result = m.explain(ctx, args.scope, args.concept)
            elif args.op == "prune-evidence":
                result = m.prune_evidence(ctx, args.before)
            elif args.op == "export":
                snap = m.export_snapshot(ctx)
                write_text(args.output, json.dumps(snap, ensure_ascii=False, indent=2, allow_nan=False))
                result = {"status": "exported", "output": str(Path(args.output).resolve()), "revision": snap["data"]["revision"]}
            elif args.op == "restore-empty":
                if not 1 <= args.max_snapshot_mib <= 512:
                    raise ValueError("max-snapshot-mib must be 1-512")
                result = m.restore_empty(ctx, read_json(args.input, args.max_snapshot_mib * 1024 * 1024))
            elif args.op == "atlas":
                write_text(args.output, atlas_html(m.get(ctx, args.scopes, session_id=args.session, now=now)))
                result = {"status": "rendered", "output": str(Path(args.output).resolve())}
            elif args.op == "health":
                result = {"status": "ok", "sqlite": sqlite3.sqlite_version, "revision": m.revision(ctx), "policy": m.policy.as_dict()}
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return 0
    except (MemoryErrorBase, ValueError, OSError, sqlite3.Error, KeyError, TypeError) as exc:
        print(json.dumps({"status": "error", "error_type": type(exc).__name__, "message": str(exc)}, ensure_ascii=False), file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())
