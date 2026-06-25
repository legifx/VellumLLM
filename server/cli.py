"""Command-line access to a single Vellum, for agents and humans.

So a CLI agent (Claude Code, Hermes, Codex, …) — or you — can query exactly one
notebook and get a source-grounded answer straight in the terminal:

    ./vellum notebooks                       # list Vellums and their ids
    ./vellum ask -n biology-101 "Define osmosis"
    ./vellum ask -n "Biology 101" "..." --json
    ./vellum ask -n biology-101 "..." --sources-only   # just the retrieved context

The answer is grounded strictly in that Vellum's files (same retrieval + prompt
as the web UI), so an agent told to "use the biology-101 Vellum" reads only
those files.
"""
from __future__ import annotations

import argparse
import json
import sys

from .cli_bridge import CLIError, build_adapter
from .config import Config
from .embeddings import build_embedder
from .notebooks import Notebook, NotebookRegistry, slugify
from .prompt import build_prompt
from .retrieval import retrieve
from .store import Store


def _registry(cfg: Config) -> NotebookRegistry:
    return NotebookRegistry(cfg.notebooks_dir)


def resolve_notebook(reg: NotebookRegistry, ref: str) -> Notebook | None:
    """Match a notebook by id, exact name, or slug/substring of the name."""
    nb = reg.get(ref)
    if nb:
        return nb
    items = reg.list()
    for n in items:
        if n.name.lower() == ref.lower():
            return n
    ref_slug = slugify(ref)
    for n in items:
        if slugify(n.name) == ref_slug or ref.lower() in n.name.lower():
            return n
    return None


def cmd_notebooks(cfg: Config, args: argparse.Namespace) -> int:
    reg = _registry(cfg)
    items = reg.list()
    if args.json:
        out = []
        for n in items:
            d = n.to_dict()
            store = Store(reg.db_path(n.id))
            d["source_count"] = len(store.list_sources())
            store.close()
            out.append(d)
        print(json.dumps(out, indent=2, ensure_ascii=False))
        return 0
    if not items:
        print("No Vellums yet. Open the web UI or create one to get started.")
        return 0
    width = max(len(n.id) for n in items)
    for n in items:
        store = Store(reg.db_path(n.id))
        count = len(store.list_sources())
        store.close()
        cat = f"  [{n.category}]" if n.category else ""
        print(f"  {n.id.ljust(width)}  {n.name}{cat}  ({count} sources)")
    return 0


def cmd_ask(cfg: Config, args: argparse.Namespace) -> int:
    reg = _registry(cfg)
    nb = resolve_notebook(reg, args.notebook)
    if nb is None:
        print(f"No Vellum matches '{args.notebook}'. Try: vellum notebooks", file=sys.stderr)
        return 2

    question = " ".join(args.question).strip()
    if not question:
        print("Ask a question, e.g. vellum ask -n my-vellum \"What is X?\"", file=sys.stderr)
        return 2

    store = Store(reg.db_path(nb.id))
    embedder = build_embedder(cfg.embedder, cfg.st_model)
    top_k = args.top_k or cfg.top_k
    chunks = retrieve(store, embedder, question, top_k)
    prompt, citations = build_prompt(question, chunks)

    if args.sources_only:
        payload = {"notebook": nb.id, "question": question,
                   "citations": [c.model_dump() for c in citations]}
        print(json.dumps(payload, indent=2, ensure_ascii=False))
        return 0

    if not chunks:
        msg = "This is not covered by the provided sources."
        if args.json:
            print(json.dumps({"notebook": nb.id, "answer": msg, "citations": []},
                             ensure_ascii=False))
        else:
            print(msg)
        return 0

    try:
        adapter = build_adapter(cfg, args.model or cfg.model)
    except CLIError as exc:
        print(str(exc), file=sys.stderr)
        return 1

    if args.json:
        try:
            answer = adapter.complete(prompt, timeout=cfg.cli_timeout)
        except CLIError as exc:
            print(json.dumps({"notebook": nb.id, "error": str(exc)}, ensure_ascii=False))
            return 1
        print(json.dumps({
            "notebook": nb.id, "answer": answer,
            "citations": [c.model_dump() for c in citations],
        }, indent=2, ensure_ascii=False))
        return 0

    # Stream the grounded answer straight to stdout.
    try:
        for piece in adapter.stream(prompt, timeout=cfg.cli_timeout):
            sys.stdout.write(piece)
            sys.stdout.flush()
    except CLIError as exc:
        print(f"\n{exc}", file=sys.stderr)
        return 1
    print()
    return 0


def build_parser() -> argparse.ArgumentParser:
    ap = argparse.ArgumentParser(prog="vellum", description="Query a single Vellum from the CLI.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    pl = sub.add_parser("notebooks", help="list Vellums and their ids")
    pl.add_argument("--json", action="store_true", help="machine-readable output")

    pa = sub.add_parser("ask", help="ask a question, answered only from one Vellum")
    pa.add_argument("-n", "--notebook", required=True, help="Vellum id or name")
    pa.add_argument("question", nargs="+", help="the question")
    pa.add_argument("--model", default="", help="model id passed to the CLI adapter")
    pa.add_argument("--top-k", type=int, default=0, help="how many chunks to retrieve")
    pa.add_argument("--json", action="store_true", help="emit {answer, citations} as JSON")
    pa.add_argument("--sources-only", action="store_true",
                    help="print retrieved citations without calling the model")
    return ap


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    cfg = Config.load()
    if args.cmd == "notebooks":
        return cmd_notebooks(cfg, args)
    if args.cmd == "ask":
        return cmd_ask(cfg, args)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
