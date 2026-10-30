"""Small question answering page over the index written by ingest.py.

The server does not use the Nutrient SDK: it only embeds the question, retrieves the
closest chunks and asks the LLM to answer from them with citations.

Usage:
  python server.py            then open http://localhost:8000
"""

from __future__ import annotations

import time
from pathlib import Path

import uvicorn
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from rag.llm import Index, answer, chat_model, embedding_model, env

ROOT = Path(__file__).resolve().parent
OUTPUT = (ROOT / env("OUTPUT_FOLDER", "output")).resolve()
DOCUMENTS = (ROOT / env("DOCUMENTS_FOLDER", "samples/documents")).resolve()
TOP_K = int(env("TOP_K", "5"))

app = FastAPI(title="Document Q&A")
index: Index | None = None


def get_index() -> Index:
    global index
    if index is None:
        if not (OUTPUT / "vectors.npy").exists():
            raise HTTPException(503, "No index yet. Run: python ingest.py")
        index = Index(OUTPUT)
    return index


class Question(BaseModel):
    question: str


@app.get("/api/config")
def config():
    return {"model": chat_model(), "embedding_model": embedding_model(), "top_k": TOP_K}


@app.get("/api/documents")
def documents():
    return get_index().documents


@app.post("/api/ask")
def ask(q: Question):
    question = q.question.strip()
    if not question:
        raise HTTPException(400, "Ask a question.")
    started = time.time()
    hits = get_index().search(question, TOP_K)
    retrieved = time.time()
    result = answer(question, hits)
    sources = []
    for n, (c, score) in enumerate(hits, start=1):
        sources.append({**c, "n": n, "score": round(score, 3), "cited": n in result["cited"]})
    return {
        "question": question,
        "answer": result["answer"],
        "cited": result["cited"],
        "sources": sources,
        "seconds": {"retrieval": round(retrieved - started, 2), "answer": round(time.time() - retrieved, 1)},
    }


@app.get("/files/{name}")
def file(name: str):
    known = {d["document"] for d in get_index().documents}
    if name not in known or not (DOCUMENTS / name).is_file():
        raise HTTPException(404)
    return FileResponse(DOCUMENTS / name)


app.mount("/", StaticFiles(directory=ROOT / "web", html=True), name="web")

if __name__ == "__main__":
    uvicorn.run(app, host=env("HOST", "127.0.0.1"), port=int(env("PORT", "8000")))
