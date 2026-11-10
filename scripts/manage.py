"""Command-line administration — bulk-load documents, inspect, re-index.

    python -m scripts.manage ingest ./examples            # files or folders
    python -m scripts.manage ingest report.pdf --replace
    python -m scripts.manage list
    python -m scripts.manage delete <doc_id>
    python -m scripts.manage reindex    # after changing the embedding model / chunking

These share the exact same code path as the web admin panel.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

from scripts._common import load_settings
from suhail.bootstrap import build_knowledge
from suhail.errors import SuhailError
from suhail.ingestion.extract import SUPPORTED_EXTENSIONS
from suhail.ingestion.service import find_unreindexable
from suhail.knowledge.registry import DocumentRegistry


def _files_under(paths: list[str]) -> list[Path]:
    found: list[Path] = []
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            found += sorted(p for p in path.rglob("*") if p.suffix.lower() in SUPPORTED_EXTENSIONS)
        else:
            found.append(path)
    return found


def cmd_ingest(args, settings) -> int:
    knowledge = build_knowledge(settings)
    failures = 0
    for path in _files_under(args.paths):
        try:
            duplicate = knowledge.ingestion.find_duplicate(path.name)
            if duplicate and not args.replace:
                print(f"SKIP  {path.name} (already ingested; use --replace)")
                continue
            record = knowledge.ingestion.ingest_file(
                path.name, path.read_bytes(), replace=bool(duplicate)
            )
            print(f"OK    {path.name} -> {record.chunk_count} chunks")
        except (SuhailError, OSError) as exc:
            failures += 1
            print(f"FAIL  {path.name}: {exc}", file=sys.stderr)
    return 1 if failures else 0


def cmd_list(_args, settings) -> int:
    records = DocumentRegistry(settings.registry_path).all()  # no models needed
    if not records:
        print("No documents.")
    for r in records:
        print(f"{r.doc_id}  {r.doc_type:<6}  {r.chunk_count:>4} chunks  {r.name}")
    return 0


def cmd_delete(args, settings) -> int:
    knowledge = build_knowledge(settings)
    if knowledge.registry.get(args.doc_id) is None:
        print(f"No such document: {args.doc_id}", file=sys.stderr)
        return 1
    knowledge.ingestion.delete(args.doc_id)
    print("Deleted.")
    return 0


def cmd_reindex(_args, settings) -> int:
    # Safety first: never discard the old index unless every document can be rebuilt.
    registry = DocumentRegistry(settings.registry_path)
    missing = find_unreindexable(registry, settings.uploads_dir)
    if missing:
        print(
            "Re-index aborted, nothing was changed. Originals missing for: "
            + ", ".join(missing)
            + ". Re-upload them first.",
            file=sys.stderr,
        )
        return 1
    knowledge = build_knowledge(settings, allow_rebuild=True)
    try:
        count = knowledge.ingestion.reindex_all()
    except SuhailError as exc:
        print(f"Re-index failed: {exc}", file=sys.stderr)
        return 1
    print(f"Re-indexed {count} documents.")
    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Suhail administration")
    sub = parser.add_subparsers(dest="command", required=True)

    ingest = sub.add_parser("ingest", help="ingest files or folders")
    ingest.add_argument("paths", nargs="+")
    ingest.add_argument("--replace", action="store_true", help="replace same-named documents")
    ingest.set_defaults(func=cmd_ingest)

    sub.add_parser("list", help="list documents").set_defaults(func=cmd_list)

    delete = sub.add_parser("delete", help="delete a document")
    delete.add_argument("doc_id")
    delete.set_defaults(func=cmd_delete)

    sub.add_parser("reindex", help="rebuild the vector index").set_defaults(func=cmd_reindex)

    args = parser.parse_args()
    settings = load_settings()
    logging.getLogger("suhail.audit").setLevel(logging.WARNING)  # keep CLI output clean
    return args.func(args, settings)


if __name__ == "__main__":
    raise SystemExit(main())
