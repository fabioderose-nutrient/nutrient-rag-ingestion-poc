"""Measure retrieval and answers on the sample questions (samples/questions.json).

For every question:
  - retrieval: is a chunk of the expected document and page among the top k?
  - answer: does the answer contain the expected values?
  - citation: does the answer cite a chunk of the expected document?
A question with no expected document must be answered with "the documents do not say"
and no citation.

Usage:
  python evaluate.py [--questions samples/questions.json] [--k 5]
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path

from rag.llm import Index, answer, chat_model, env

ROOT = Path(__file__).resolve().parent


def norm(s: str) -> str:
    return re.sub(r"\s+", " ", s.lower()).strip()


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--questions", default="samples/questions.json")
    parser.add_argument("--k", type=int, default=int(env("TOP_K", "5")))
    args = parser.parse_args()

    index = Index((ROOT / env("OUTPUT_FOLDER", "output")).resolve())
    questions = json.loads((ROOT / args.questions).read_text(encoding="utf-8"))
    rows = []
    for q in questions:
        started = time.time()
        hits = index.search(q["question"], args.k)
        result = answer(q["question"], hits)
        seconds = time.time() - started
        expected_pages = q["page"] if isinstance(q["page"], list) else [q["page"]]
        cited = [hits[n - 1][0] for n in result["cited"]]
        if q["document"]:
            ranks = [i + 1 for i, (c, _) in enumerate(hits)
                     if c["document"] == q["document"] and any(c["page"] <= p <= c["page_end"] for p in expected_pages)]
            retrieved = bool(ranks)
            # Each expected value is a string, or a list of accepted wordings.
            answered = all(any(norm(v) in norm(result["answer"]) for v in ([a] if isinstance(a, str) else a))
                           for a in q["answer"])
            cited_ok = any(c["document"] == q["document"] for c in cited)
        else:
            ranks, retrieved = [], None
            answered = bool(re.search(r"(do|does) not (say|mention|contain|state|include)|not (mentioned|stated|available|found|provided)",
                                      result["answer"].lower()))
            cited_ok = not result["cited"]
        rows.append({
            "question": q["question"], "document": q["document"], "retrieved": retrieved,
            "rank": ranks[0] if ranks else None, "answer_ok": answered, "citation_ok": cited_ok,
            "answer": result["answer"], "seconds": round(seconds, 1),
        })
        mark = lambda v: "-" if v is None else ("yes" if v else "NO")
        print(f"{q['question'][:62]:<62} retrieved {mark(retrieved):<3} rank {str(ranks[0]) if ranks else '-':<2} "
              f"answer {mark(answered):<3} cited {mark(cited_ok):<3} {seconds:5.1f}s")

    answerable = [r for r in rows if r["document"]]
    summary = {
        "model": chat_model(),
        "k": args.k,
        "questions": len(rows),
        "retrieval_hit_at_k": sum(r["retrieved"] for r in answerable),
        "answerable": len(answerable),
        "answers_correct": sum(r["answer_ok"] for r in rows),
        "citations_correct": sum(r["citation_ok"] for r in rows),
        "mean_seconds": round(sum(r["seconds"] for r in rows) / len(rows), 1),
    }
    print()
    print(f"Retrieval: expected page in the top {args.k} for {summary['retrieval_hit_at_k']}/{summary['answerable']} questions")
    print(f"Answers:   {summary['answers_correct']}/{summary['questions']} correct, "
          f"citations {summary['citations_correct']}/{summary['questions']} correct, {summary['mean_seconds']}s per question")
    out = ROOT / env("OUTPUT_FOLDER", "output") / "evaluation.json"
    out.write_text(json.dumps({"summary": summary, "questions": rows}, indent=1), encoding="utf-8")
    print(f"Written: {out.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
