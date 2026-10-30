// Ask a question, show the answer with its citations and the cited passages.
const $ = (id) => document.getElementById(id);
const esc = (s) => String(s ?? "").replace(/[&<>"]/g, (c) => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;" }[c]));

const EXAMPLES = [
  "By how much did electricity use fall at North House in 2026?",
  "When is the next boiler service due at River Court?",
  "Do contractors need an escort for hot work?",
  "Which ticket took the longest to close, and why?",
];

async function init() {
  const config = await (await fetch("/api/config")).json();
  $("models").textContent = `Answers: ${config.model} · Embeddings: ${config.embedding_model} · Top ${config.top_k} chunks`;
  $("examples").innerHTML = EXAMPLES.map((q) => `<button type="button">${esc(q)}</button>`).join("");
  for (const b of $("examples").querySelectorAll("button")) b.onclick = () => { $("question").value = b.textContent; ask(); };
  $("askForm").onsubmit = (e) => { e.preventDefault(); ask(); };
  const res = await fetch("/api/documents");
  if (!res.ok) { $("status").textContent = "No index yet. Run python ingest.py first."; return; }
  const docs = await res.json();
  $("docs").innerHTML = `<tr><th>Document</th><th>Pages</th><th>Method</th><th>Chunks</th></tr>` +
    docs.map((d) => `<tr><td><a href="/files/${encodeURIComponent(d.document)}" target="_blank">${esc(d.document)}</a></td>
      <td class="num">${d.pages}</td><td>${esc(d.method)}</td><td class="num">${d.chunks}</td></tr>`).join("");
}

async function ask() {
  const question = $("question").value.trim();
  if (!question) return;
  $("askButton").disabled = true;
  $("status").textContent = "Searching the documents and writing the answer...";
  $("result").hidden = true;
  try {
    const res = await fetch("/api/ask", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ question }) });
    const data = await res.json();
    if (!res.ok) throw new Error(data.detail || res.statusText);
    render(data);
    $("status").textContent = "";
  } catch (err) {
    $("status").textContent = `Failed: ${err.message}`;
  } finally {
    $("askButton").disabled = false;
  }
}

function render(data) {
  $("result").hidden = false;
  $("answer").innerHTML = esc(data.answer).replace(/\[([\d,\s]+)\]/g, (m, group) =>
    group.split(/[,\s]+/).filter(Boolean).map((n) => `<a class="cite" href="#src-${n}" data-n="${n}">${n}</a>`).join(" "));
  $("timing").textContent = `Retrieval ${data.seconds.retrieval}s · answer ${data.seconds.answer}s`;
  const sources = [...data.sources].sort((a, b) => (b.cited - a.cited) || (a.n - b.n));
  $("sources").innerHTML = sources.map((s) => {
    const pages = s.page === s.page_end ? `page ${s.page}` : `pages ${s.page}-${s.page_end}`;
    const link = s.document.toLowerCase().endsWith(".pdf") ? `/files/${encodeURIComponent(s.document)}#page=${s.page}` : `/files/${encodeURIComponent(s.document)}`;
    return `<div class="source ${s.cited ? "cited" : ""}" id="src-${s.n}">
      <div class="source-head">
        <span class="where">[${s.n}] <a href="${link}" target="_blank">${esc(s.document)}</a>, ${pages}<span class="badge">${esc(s.kind)}</span></span>
        <span class="muted small">${s.cited ? "cited" : "retrieved, not cited"} · similarity ${s.score.toFixed(2)}</span>
      </div>
      ${s.headings.length ? `<div class="section">${esc(s.headings.join(" › "))}</div>` : ""}
      <div class="passage">${markdown(s.text)}</div>
    </div>`;
  }).join("");
  for (const a of $("answer").querySelectorAll(".cite")) a.onclick = (e) => {
    e.preventDefault();
    const el = $(`src-${a.dataset.n}`);
    if (!el) return;
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    el.classList.add("flash");
    setTimeout(() => el.classList.remove("flash"), 900);
  };
}

// Just enough Markdown for a passage: pipe tables, fenced blocks, list items, paragraphs.
function markdown(text) {
  // Layout text (scans, spreadsheets) is one fenced block: keep its columns as they are.
  if (text.trim().startsWith("```")) return `<pre>${esc(text.trim().replace(/^```\w*\n?/, "").replace(/\n?```$/, ""))}</pre>`;
  const out = [];
  const blocks = text.split(/\n{2,}/);
  for (const block of blocks) {
    const lines = block.split("\n");
    if (block.startsWith("```")) {
      out.push(`<pre>${esc(lines.filter((l) => !l.startsWith("```")).join("\n"))}</pre>`);
    } else if (lines.every((l) => l.trim().startsWith("|"))) {
      const rows = lines.filter((l) => !/^\s*\|?\s*:?-{3,}/.test(l)).map((l) => l.trim().replace(/^\||\|$/g, "").split("|"));
      out.push(`<table>${rows.map((r, i) => `<tr>${r.map((c) => i === 0 ? `<th>${esc(c.trim())}</th>` : `<td>${esc(c.trim())}</td>`).join("")}</tr>`).join("")}</table>`);
    } else {
      out.push(`<p>${esc(block).replace(/\n/g, "<br>")}</p>`);
    }
  }
  return out.join("");
}

init();
