"""Embeddings, retrieval and answers through OpenAI-compatible endpoints (a local Ollama by default)."""

from __future__ import annotations

import json
import os
import re
from pathlib import Path

import numpy as np
from openai import OpenAI


def env(name: str, default: str = "") -> str:
    value = os.environ.get(name, "").strip()
    return value or default


def chat_client() -> OpenAI:
    return OpenAI(base_url=env("LLM_BASE_URL", "http://localhost:11434/v1"), api_key=env("LLM_API_KEY", "not-needed"))


def embedding_client() -> OpenAI:
    base = env("EMBEDDING_BASE_URL", env("LLM_BASE_URL", "http://localhost:11434/v1"))
    return OpenAI(base_url=base, api_key=env("EMBEDDING_API_KEY", env("LLM_API_KEY", "not-needed")))


def chat_model() -> str:
    return env("LLM_MODEL", "qwen2.5:7b-instruct")


def embedding_model() -> str:
    return env("EMBEDDING_MODEL", "nomic-embed-text")


# nomic-embed-text is trained with these task prefixes. Other models ignore them harmlessly.
DOC_PREFIX = "search_document: "
QUERY_PREFIX = "search_query: "


def embed(texts: list[str], prefix: str) -> np.ndarray:
    client = embedding_client()
    vectors = []
    for start in range(0, len(texts), 32):
        batch = [prefix + t for t in texts[start:start + 32]]
        response = client.embeddings.create(model=embedding_model(), input=batch)
        vectors.extend(item.embedding for item in response.data)
    m = np.array(vectors, dtype=np.float32)
    return m / np.linalg.norm(m, axis=1, keepdims=True)


class Index:
    """Chunks and their normalised embeddings, as written by ingest.py."""

    def __init__(self, folder: Path):
        self.folder = folder
        self.chunks: list[dict] = json.loads((folder / "chunks.json").read_text(encoding="utf-8"))
        self.vectors = np.load(folder / "vectors.npy")
        self.documents: list[dict] = json.loads((folder / "documents.json").read_text(encoding="utf-8"))

    def search(self, question: str, k: int) -> list[tuple[dict, float]]:
        q = embed([question], QUERY_PREFIX)[0]
        scores = self.vectors @ q
        best = np.argsort(-scores)[:k]
        return [(self.chunks[i], float(scores[i])) for i in best]


SYSTEM = (
    "You answer questions about a company's documents. Use only the numbered sources. "
    "Cite every fact with the number of its source in square brackets, for example [2]. "
    "Copy figures, dates and names exactly as they appear in the sources. "
    "If the sources do not contain the answer, say that the documents do not say, and cite nothing. "
    "Answer in at most four sentences."
)


def source_label(chunk: dict) -> str:
    pages = f"page {chunk['page']}" if chunk["page"] == chunk["page_end"] else f"pages {chunk['page']}-{chunk['page_end']}"
    section = " > ".join(chunk["headings"])
    return f"{chunk['document']}, {pages}" + (f", section: {section}" if section else "")


def answer(question: str, hits: list[tuple[dict, float]]) -> dict:
    sources = "\n\n".join(f"[{n}] {source_label(c)}\n{c['text']}" for n, (c, _) in enumerate(hits, start=1))
    response = chat_client().chat.completions.create(
        model=chat_model(),
        temperature=0,
        messages=[
            {"role": "system", "content": SYSTEM},
            {"role": "user", "content": f"Sources:\n\n{sources}\n\nQuestion: {question}"},
        ],
    )
    text = (response.choices[0].message.content or "").strip()
    numbers = [int(n) for group in re.findall(r"\[([\d,\s]+)\]", text) for n in re.findall(r"\d+", group)]
    cited = sorted({n for n in numbers if 1 <= n <= len(hits)})
    return {"answer": text, "cited": cited}
