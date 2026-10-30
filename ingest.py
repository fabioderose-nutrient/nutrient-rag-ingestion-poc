"""Prepare a folder of documents for retrieval-augmented generation.

  1. Convert every document to Markdown with the Nutrient Python SDK (OCR for scans).
  2. Split the Markdown into chunks that keep headings, tables and page numbers.
  3. Embed the chunks with a local embedding model and save the index.

Output (OUTPUT_FOLDER, default output/):
  markdown/<document>.md   the converted Markdown, with page markers
  chunks.json              every chunk with document, pages, headings and text
  chunks.jsonl             the same, one chunk per line, for other vector stores
  vectors.npy              normalised embeddings, one row per chunk
  documents.json           one entry per document: pages, method, chunks, seconds

Usage:
  python ingest.py [--input samples/documents] [--output output] [--no-embed]
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from pathlib import Path

import numpy as np

from rag.chunking import chunk
from rag.convert import SUPPORTED, convert
from rag.llm import DOC_PREFIX, embed, embedding_model, env

ROOT = Path(__file__).resolve().parent


def slug(name: str) -> str:
    return "".join(ch if ch.isalnum() else "-" for ch in Path(name).stem.lower()).strip("-")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", default=env("DOCUMENTS_FOLDER", "samples/documents"))
    parser.add_argument("--output", default=env("OUTPUT_FOLDER", "output"))
    parser.add_argument("--no-embed", action="store_true", help="convert and chunk only")
    args = parser.parse_args()

    source = (ROOT / args.input).resolve()
    out = (ROOT / args.output).resolve()
    (out / "markdown").mkdir(parents=True, exist_ok=True)
    files = sorted(p for p in source.iterdir() if p.suffix.lower() in SUPPORTED)
    if not files:
        print(f"No supported documents in {source}", file=sys.stderr)
        return 1

    chunks, documents = [], []
    for path in files:
        started = time.time()
        converted = convert(path)
        prefix = slug(path.name)
        (out / "markdown" / f"{prefix}.md").write_text(converted.markdown, encoding="utf-8")
        parts = chunk(converted.markdown, path.name, prefix)
        seconds = round(time.time() - started, 1)
        documents.append({
            "document": path.name, "pages": converted.pages, "method": converted.method,
            "chunks": len(parts), "tables": sum(c.kind == "table" for c in parts),
            "seconds": seconds,
        })
        chunks.extend(parts)
        print(f"{path.name:<40} {converted.pages:>2} pages  {converted.method:<15} {len(parts):>3} chunks  {seconds:>5}s")

    titles = {d["document"]: Path(d["document"]).stem.replace("-", " ") for d in documents}
    records = [c.to_dict() for c in chunks]
    (out / "chunks.json").write_text(json.dumps(records, indent=1, ensure_ascii=False), encoding="utf-8")
    (out / "chunks.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records), encoding="utf-8")
    (out / "documents.json").write_text(json.dumps(documents, indent=1), encoding="utf-8")
    print(f"{len(chunks)} chunks from {len(documents)} documents written to {out}")

    if not args.no_embed:
        started = time.time()
        vectors = embed([c.embedding_text(titles[c.document]) for c in chunks], DOC_PREFIX)
        np.save(out / "vectors.npy", vectors)
        print(f"Embedded with {embedding_model()} in {time.time() - started:.1f}s: {vectors.shape[0]} x {vectors.shape[1]}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
