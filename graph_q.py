#!/usr/bin/env python3
"""
Query helper for the knowledge graph produced into graph_output/.

Designed to give terse, grep-friendly answers so an LLM (or you) can answer
"where is X / who calls Y / what does Z import" without reading 100s of files.

Usage:
  python graph_q.py find <name>            # fuzzy-find by node name (substring, case-insensitive)
  python graph_q.py where <name>           # exact match → file:line
  python graph_q.py in-file <path>         # list classes + functions defined in a file
  python graph_q.py callers <name>         # who calls this function/method?
  python graph_q.py callees <name>         # what does it call?
  python graph_q.py imports-of <module>    # who imports this module?
  python graph_q.py imports-by <file>      # what does this file import?
  python graph_q.py inherits <class>       # parent classes + child classes
  python graph_q.py stats                  # summary metrics

Graph selection:
  - Default: newest graph_YYYYMMDD_HHMMSS.json under graph_output/
  - Override with --graph <path>  or  env var SLMS_GRAPH=<path>

Output:
  One result per line — kind, qualified-id, file:line. Empty output = no matches.
"""
from __future__ import annotations
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Iterable

REPO_ROOT = Path(__file__).resolve().parent
GRAPH_DIR = REPO_ROOT / "graph_output"


# ── Graph loading ────────────────────────────────────────────────────────

def _latest_graph_path() -> Path:
    candidates = sorted(GRAPH_DIR.glob("graph_*.json"))
    if not candidates:
        sys.exit(f"No graph_*.json files in {GRAPH_DIR}")
    return candidates[-1]


def load_graph(path: Path | None = None) -> dict:
    p = path or Path(os.environ.get("SLMS_GRAPH") or _latest_graph_path())
    with p.open(encoding="utf-8") as f:
        return json.load(f)


# ── Helpers ──────────────────────────────────────────────────────────────

def _short(node_id: str) -> str:
    """Strip the verbose `file:...:class:...:method:` prefixes for readable output."""
    parts = node_id.split(":")
    # Keep the last meaningful segment, plus class context if present
    cls = None
    for i, p in enumerate(parts):
        if p == "class" and i + 1 < len(parts):
            cls = parts[i + 1]
    if parts[-2] in ("method", "function"):
        leaf = parts[-1]
        return f"{cls}.{leaf}" if cls else leaf
    return parts[-1] or node_id


def _fmt(node: dict) -> str:
    fp = node.get("file_path") or "?"
    ln = node.get("line_number")
    loc = f"{fp}:{ln}" if ln else fp
    name = _short(node["id"])
    return f"{node['node_type']:9s} {name:40s} {loc}"


def _iter_matches(nodes: Iterable[dict], name: str, exact: bool) -> list[dict]:
    q = name.lower()
    out = []
    for n in nodes:
        nm = (n.get("name") or "").lower()
        if (nm == q) if exact else (q in nm):
            out.append(n)
    return out


# ── Commands ─────────────────────────────────────────────────────────────

def cmd_find(g: dict, name: str) -> None:
    matches = _iter_matches(g["nodes"], name, exact=False)
    for n in matches:
        print(_fmt(n))


def cmd_where(g: dict, name: str) -> None:
    matches = _iter_matches(g["nodes"], name, exact=True)
    for n in matches:
        print(_fmt(n))


def cmd_in_file(g: dict, path: str) -> None:
    needle = path.replace("\\", "/").lower()
    rows = []
    for n in g["nodes"]:
        if n["node_type"] not in ("class", "function"):
            continue
        fp = (n.get("file_path") or "").replace("\\", "/").lower()
        if needle in fp:
            rows.append(n)
    rows.sort(key=lambda r: (r.get("file_path") or "", r.get("line_number") or 0))
    for n in rows:
        print(_fmt(n))


def _resolve_to_ids(g: dict, name: str) -> list[str]:
    """Map a user-typed name → matching node IDs (exact, then fuzzy fallback)."""
    exact = [n["id"] for n in _iter_matches(g["nodes"], name, exact=True)]
    if exact:
        return exact
    return [n["id"] for n in _iter_matches(g["nodes"], name, exact=False)]


def cmd_callers(g: dict, name: str) -> None:
    targets = set(_resolve_to_ids(g, name))
    if not targets:
        return
    by_id = {n["id"]: n for n in g["nodes"]}
    for e in g["edges"]:
        if e["edge_type"] != "calls":
            continue
        if e["target"] in targets:
            caller = by_id.get(e["source"])
            if caller:
                print(_fmt(caller))


def cmd_callees(g: dict, name: str) -> None:
    sources = set(_resolve_to_ids(g, name))
    if not sources:
        return
    by_id = {n["id"]: n for n in g["nodes"]}
    for e in g["edges"]:
        if e["edge_type"] != "calls":
            continue
        if e["source"] in sources:
            callee = by_id.get(e["target"])
            if callee:
                print(_fmt(callee))
            else:
                # external symbol — no node, just show the raw target
                print(f"external  {_short(e['target']):40s} (no node)")


def cmd_imports_of(g: dict, module: str) -> None:
    q = module.lower()
    by_id = {n["id"]: n for n in g["nodes"]}
    for e in g["edges"]:
        if e["edge_type"] != "imports":
            continue
        if q in e["target"].lower():
            src = by_id.get(e["source"])
            print(f"{_short(e['source']):40s} → {_short(e['target'])}"
                  + (f"   ({src['file_path']})" if src and src.get('file_path') else ""))


def cmd_imports_by(g: dict, file_path: str) -> None:
    needle = file_path.replace("\\", "/").lower()
    by_id = {n["id"]: n for n in g["nodes"]}
    for e in g["edges"]:
        if e["edge_type"] != "imports":
            continue
        src = by_id.get(e["source"])
        if not src:
            continue
        if needle in (src.get("file_path") or "").replace("\\", "/").lower():
            print(_short(e["target"]))


def cmd_inherits(g: dict, name: str) -> None:
    targets = set(_resolve_to_ids(g, name))
    if not targets:
        return
    by_id = {n["id"]: n for n in g["nodes"]}
    print("== Inherits from (parents): ==")
    for e in g["edges"]:
        if e["edge_type"] == "inherits" and e["source"] in targets:
            parent = by_id.get(e["target"])
            print(_fmt(parent) if parent else f"external  {_short(e['target'])}")
    print("== Inherited by (children): ==")
    for e in g["edges"]:
        if e["edge_type"] == "inherits" and e["target"] in targets:
            child = by_id.get(e["source"])
            if child:
                print(_fmt(child))


def cmd_stats(g: dict) -> None:
    md = g.get("metadata", {})
    stats = md.get("stats", {})
    metrics = md.get("metrics", {})
    print(f"Generated: {md.get('generated_at', '?')}")
    print(f"Files analyzed:  {stats.get('files_analyzed')}")
    print(f"Classes:         {stats.get('classes_found')}")
    print(f"Functions:       {stats.get('functions_found')}")
    print(f"Imports:         {stats.get('imports_found')}")
    print(f"Nodes / Edges:   {metrics.get('nodes')} / {metrics.get('edges')}")
    print()
    print("Most imported modules:")
    for mod, cnt in metrics.get("most_imported_modules", [])[:10]:
        print(f"  {cnt:3d}  {mod.replace('module:', '')}")
    print()
    print("Files with the most outgoing dependencies:")
    for f, cnt in metrics.get("most_dependent_files", [])[:10]:
        print(f"  {cnt:3d}  {f.replace('file:', '')}")


# ── Entry point ──────────────────────────────────────────────────────────

COMMANDS = {
    "find":        ("name",       cmd_find),
    "where":       ("name",       cmd_where),
    "in-file":     ("path",       cmd_in_file),
    "callers":     ("name",       cmd_callers),
    "callees":     ("name",       cmd_callees),
    "imports-of":  ("module",     cmd_imports_of),
    "imports-by":  ("file",       cmd_imports_by),
    "inherits":    ("class",      cmd_inherits),
    "stats":       (None,         cmd_stats),
}


def main(argv: list[str]) -> int:
    parser = argparse.ArgumentParser(
        prog="graph_q",
        description="Query the knowledge graph in graph_output/. See file header for examples.",
    )
    parser.add_argument("--graph", help="Path to a specific graph_*.json (default: newest)")
    parser.add_argument("command", choices=COMMANDS.keys(), help="Query type")
    parser.add_argument("arg", nargs="?", help="Argument for the command (name / path / module)")
    args = parser.parse_args(argv)

    arg_label, fn = COMMANDS[args.command]
    if arg_label is not None and not args.arg:
        parser.error(f"'{args.command}' requires a <{arg_label}> argument")

    g = load_graph(Path(args.graph) if args.graph else None)
    if arg_label is None:
        fn(g)
    else:
        fn(g, args.arg)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
