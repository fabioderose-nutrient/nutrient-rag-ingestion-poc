"""Convert documents to Markdown with the Nutrient Python SDK.

Each document becomes one Markdown file with a marker at the start of every page
(<!-- nutrient-page-start: N -->).

- PDF with a text layer, Word: Markdown export, with headings as # lines and tables as
  pipe tables.
- Scanned PDF: OCR (PdfEditor.make_searchable) in memory, then the layout text export,
  which keeps table rows on one line with their columns aligned.
- Spreadsheet: layout text export, one sheet per page.

The layout text is kept as a fenced block per page. On the sample spreadsheet and on the
OCR output of the scanned letter, the layout text export keeps every table row together,
while the Markdown export does not (see the README).
"""

from __future__ import annotations

import os
import re
import tempfile
from dataclasses import dataclass
from pathlib import Path

import nutrient_sdk as ns

PAGE_MARKER = re.compile(r"<!--\s*nutrient-page-start:\s*(\d+)\s*-->")
SPREADSHEETS = {".xlsx"}
SUPPORTED = {".pdf", ".docx"} | SPREADSHEETS

# Below this many letters and digits per page, a PDF is treated as a scan and read with OCR.
MIN_CHARS_PER_PAGE = 40

_licensed = False


def register_license() -> None:
    """Register NUTRIENT_LICENSE_KEY once. Empty = evaluation mode."""
    global _licensed
    if _licensed:
        return
    key = os.environ.get("NUTRIENT_LICENSE_KEY", "").strip()
    if key:
        ns.License.register_key(key)
    _licensed = True


@dataclass
class Converted:
    markdown: str
    pages: int
    method: str  # "markdown", "ocr + layout text" or "layout text"


def _markdown(path: Path, out: Path) -> tuple[str, int]:
    with ns.Document.open(str(path)) as doc:
        settings = doc.settings.markdown_settings
        settings.emit_page_boundary_markers = True
        settings.use_html_tables = False
        settings.join_hyphenated_line_breaks = True
        settings.include_headers_and_footers = False
        doc.export_as_markdown(str(out))
        pages = doc.page_count
    return out.read_text(encoding="utf-8", errors="replace"), pages


def _fenced_pages(text: str) -> str:
    """Wrap the text of every page in a fenced block under its page marker."""
    parts = PAGE_MARKER.split(text)
    md = []
    for i in range(1, len(parts), 2):
        body = parts[i + 1].strip("\n")
        if body.strip():
            md.append(f"<!-- nutrient-page-start: {parts[i]} -->\n\n```text\n{body}\n```\n")
    return "\n".join(md) if md else text


def _layout_text(path: Path, out: Path, ocr: bool = False) -> tuple[str, int]:
    with ns.Document.open(str(path)) as doc:
        editor = None
        if ocr:
            # OCR adds a text layer to every page of the document in memory. Nothing is saved:
            # a saved copy would carry the evaluation watermark, which OCR would then read.
            editor = ns.PdfEditor.edit(doc)
            editor.make_searchable()
        doc.settings.text_settings.emit_page_boundary_markers = True
        doc.export_as_text(str(out))
        pages = doc.page_count
        if editor is not None:
            editor.close()
    return _fenced_pages(out.read_text(encoding="utf-8", errors="replace")), pages


def text_chars(markdown: str) -> int:
    return sum(ch.isalnum() for ch in PAGE_MARKER.sub("", markdown))


def convert(path: Path) -> Converted:
    register_license()
    suffix = path.suffix.lower()
    with tempfile.TemporaryDirectory() as tmp:
        tmp = Path(tmp)
        if suffix in SPREADSHEETS:
            text, pages = _layout_text(path, tmp / "out.txt")
            return Converted(text, pages, "layout text")
        md, pages = _markdown(path, tmp / "out.md")
        if suffix == ".pdf" and text_chars(md) < MIN_CHARS_PER_PAGE * max(pages, 1):
            text, pages = _layout_text(path, tmp / "out.txt", ocr=True)
            return Converted(text, pages, "ocr + layout text")
        return Converted(md, pages, "markdown")
