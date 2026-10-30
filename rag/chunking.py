"""Split the Markdown of one document into retrieval chunks.

A chunk never crosses a heading, so it belongs to one section. Tables are kept whole in
their own chunk. Layout text (scans and spreadsheets) is split only at blank lines and at
short title lines, so the rows of a table stay together with their columns aligned. Every
chunk records the document, the pages it comes from and the headings above it, so an answer
can cite "report.pdf, page 2".
"""

from __future__ import annotations

import re
from dataclasses import asdict, dataclass, field

from .convert import PAGE_MARKER

HEADING = re.compile(r"^(#{1,6})\s+(.*\S)\s*$")
NUMBERED = re.compile(r"^(\d+(?:\.\d+)*)\.?\s")
PAGE_NUMBER = re.compile(r"^(page\s+)?\d+(\s+of\s+\d+)?$", re.IGNORECASE)
MAX_CHARS = 1200
MAX_LAYOUT_CHARS = 2400


@dataclass
class Chunk:
    id: str
    document: str
    page: int
    page_end: int
    headings: list[str]
    kind: str  # "text", "table" or "layout"
    text: str
    chars: int = 0
    extra: dict = field(default_factory=dict)

    def embedding_text(self, title: str) -> str:
        """What gets embedded: the document and section context, then the passage."""
        context = " > ".join(self.headings)
        return f"Document: {title}\nSection: {context}\n\n{self.text}" if context else f"Document: {title}\n\n{self.text}"

    def to_dict(self) -> dict:
        d = asdict(self)
        d.pop("extra")
        return d


def heading_level(markdown_level: int, text: str) -> int:
    """The level of a numbered heading comes from its numbering ("3.1 Lifts" is level 2),
    which is more reliable than the font size the converter saw."""
    numbered = NUMBERED.match(text)
    return numbered.group(1).count(".") + 1 if numbered else markdown_level


def strip_running_lines(markdown: str) -> str:
    """Drop page numbers and the running header or footer lines repeated on most pages."""
    pages = PAGE_MARKER.split(markdown)[2::2] or [markdown]
    counts: dict[str, int] = {}
    for page in pages:
        for line in {l.strip() for l in page.splitlines()}:
            counts[line] = counts.get(line, 0) + 1

    def running(line: str) -> bool:
        t = line.strip()
        if not t or t[0] in "|#<`":
            return False
        if PAGE_NUMBER.match(t):
            return True
        return len(pages) >= 3 and len(t) < 120 and counts.get(t, 0) >= max(3, len(pages) / 2)

    return "\n".join(l for l in markdown.splitlines() if not running(l))


def _blocks(markdown: str):
    """Yield (page, kind, text) blocks: heading, paragraph, table or code."""
    page = 1
    buf: list[str] = []
    kind = None
    in_code = False

    def flush():
        nonlocal buf, kind
        if buf and any(line.strip() for line in buf):
            yield page, kind, "\n".join(buf).strip("\n")
        buf, kind = [], None

    for line in markdown.splitlines():
        marker = PAGE_MARKER.search(line)
        if marker and not in_code:
            yield from flush()
            page = int(marker.group(1))
            continue
        if line.startswith("```"):
            if in_code:
                buf.append(line)
                in_code = False
                yield from flush()
            else:
                yield from flush()
                in_code, kind, buf = True, "layout", [line]
            continue
        if in_code:
            buf.append(line)
            continue
        heading = HEADING.match(line)
        if heading:
            yield from flush()
            text = heading.group(2).strip()
            yield page, f"h{heading_level(len(heading.group(1)), text)}", text
            continue
        is_table = line.lstrip().startswith("|")
        if not line.strip():
            if kind != "table":
                yield from flush()
            continue
        if is_table and kind != "table":
            yield from flush()
            kind = "table"
        elif not is_table and kind == "table":
            yield from flush()
        kind = kind or "text"
        buf.append(line)
    yield from flush()


def _is_title(line: str, following: str) -> bool:
    """A short line without final punctuation followed by a longer one, such as "Next service"."""
    t = line.strip()
    return (2 < len(t) <= 40 and t[0].isupper() and t[-1] not in ".,;:" and "  " not in t
            and not any(ch.isdigit() for ch in t) and len(following.strip()) > len(t))


def _split_layout(block: str) -> list[tuple[str | None, str]]:
    """Split a fenced layout block (OCR or spreadsheet text) into (title, fenced text) parts.

    Layout text has no Markdown headings, so a new part starts at every blank line that
    follows a full part and at every title-like line. Parts stay under MAX_LAYOUT_CHARS.
    """
    lines = [l for l in block.splitlines() if not l.startswith("```")]
    sections: list[tuple[str | None, list[str]]] = [(None, [])]
    for i, line in enumerate(lines):
        following = next((l for l in lines[i + 1:] if l.strip()), "")
        if _is_title(line, following) and sections[-1][1]:
            sections.append((line.strip(), []))
        elif _is_title(line, following) and sections[-1][0] is None:
            sections[-1] = (line.strip(), [])
        sections[-1][1].append(line)
    parts: list[tuple[str | None, list[str]]] = []
    for title, body in sections:
        text = "\n".join(body).strip("\n")
        if not text.strip():
            continue
        # Very short sections (a title and a line or two) join the next one.
        if parts and len("\n".join(parts[-1][1])) < 120:
            parts[-1] = (parts[-1][0], parts[-1][1] + [text])
        elif parts and len("\n".join(parts[-1][1])) + len(text) <= 300:
            parts[-1] = (parts[-1][0], parts[-1][1] + [text])
        else:
            parts.append((title, [text]))
    out = []
    for title, body in parts:
        text = "\n".join(body)
        while len(text) > MAX_LAYOUT_CHARS:
            cut = text.rfind("\n\n", 0, MAX_LAYOUT_CHARS)
            cut = cut if cut > 0 else text.rfind("\n", 0, MAX_LAYOUT_CHARS)
            out.append((title, "```text\n" + text[:cut].strip("\n") + "\n```"))
            text = text[cut:].strip("\n")
        out.append((title, "```text\n" + text + "\n```"))
    return out


def chunk(markdown: str, document: str, prefix: str) -> list[Chunk]:
    chunks: list[Chunk] = []
    headings: list[tuple[int, str]] = []
    current: list[tuple[int, str]] = []  # (page, paragraph) of the text chunk being built

    def path() -> list[str]:
        return [h for _, h in headings]

    def emit(kind: str, parts: list[tuple[int, str]]):
        if not parts:
            return
        text = "\n\n".join(p for _, p in parts).strip()
        if not text:
            return
        chunks.append(Chunk(
            id=f"{prefix}-{len(chunks) + 1:03d}", document=document,
            page=parts[0][0], page_end=parts[-1][0], headings=path(),
            kind=kind, text=text, chars=len(text)))

    for page, kind, text in _blocks(strip_running_lines(markdown)):
        if kind.startswith("h"):
            emit("text", current)
            current = []
            level = int(kind[1:])
            headings = [(lvl, h) for lvl, h in headings if lvl < level] + [(level, text)]
            continue
        if kind == "layout":
            emit("text", current)
            current = []
            for title, part in _split_layout(text):
                saved = headings
                if title:
                    headings = headings + [(9, title)]
                emit("layout", [(page, part)])
                headings = saved
            continue
        if kind == "table":
            # A short paragraph right before a table is usually its caption: keep them together.
            caption = current[-1:] if current and len(current[-1][1]) < 200 else []
            emit("text", current[:-1] if caption else current)
            current = []
            emit(kind, caption + [(page, text)])
            continue
        if current and sum(len(t) for _, t in current) + len(text) > MAX_CHARS:
            emit("text", current)
            current = []
        current.append((page, " ".join(text.split()) if not text.lstrip().startswith("- ") else text))
    emit("text", current)
    return chunks
