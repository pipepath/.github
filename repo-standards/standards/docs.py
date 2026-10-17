"""Documentation checks (spec §3.1, §3.3)."""

import os
import re
from pathlib import Path
from urllib.parse import unquote

REQUIRED = ["README.md", "docs/README.md", ".github/pull_request_template.md", ".github/workflows/standards.yml"]
GLOSSARY = "docs/glosario.md"


def human_docs(root):
    root = Path(root)
    out = []
    docs_dir = root / "docs"
    if docs_dir.is_dir():
        for p in docs_dir.rglob("*.md"):
            rel = p.relative_to(root)
            if rel.parts[:2] == ("docs", "superpowers") or rel == Path("docs/README.md"):
                continue
            out.append(rel)
    for p in root.glob("*/README.md"):
        rel = p.relative_to(root)
        if rel.parts[0] not in ("docs", ".github", ".claude", "org-rules", "logs", "knowledge", "node_modules") and not rel.parts[0].startswith("."):
            out.append(rel)
    return sorted(out, key=str)


def check_files(root, report):
    root = Path(root)
    for rel in REQUIRED:
        if not (root / rel).is_file():
            report.add("files", "FAIL", rel, "required file is missing")
    if len([p for p in human_docs(root) if p != Path(GLOSSARY)]) >= 2 and not (root / GLOSSARY).is_file():
        report.add("files", "FAIL", GLOSSARY, "required once the repository has two or more human docs")


README_WARN, README_FAIL = 120, 240
DOC_WARN, DOC_FAIL = 150, 300
FENCE = re.compile(r"^(```|~~~)")
INLINE = re.compile(r"`[^`\n]*`")
HTML_COMMENT = re.compile(r"<!--.*?-->", re.S)
BLOCK_START = re.compile(r"^(#|\||```|~~~|>|[-*+]\s|\d+[.)]\s)")
LINK = re.compile(r"\[[^\]]*\]\(([^)\s]+)(?:\s+\"[^\"]*\")?\)")


def read(root, rel, report):
    """Read a doc as UTF-8; on failure WARN once per file and return None so the caller skips it."""
    try:
        return (Path(root) / rel).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        path = str(rel)
        if not any(f.check == "unreadable" and f.path == path for f in report.findings):
            report.add("unreadable", "WARN", path, "cannot read file (%s); check it by hand" % type(e).__name__)
        return None


def present(root, rel):
    """True if something exists at rel, even a directory or a broken symlink (read() then warns)."""
    return os.path.lexists(Path(root) / rel)


def strip_code(text):
    out, fenced = [], False
    for line in text.split("\n"):
        if FENCE.match(line.strip()):
            fenced = not fenced
            out.append("")
            continue
        out.append("" if fenced else INLINE.sub("", line))
    return "\n".join(out)


def _length(report, rel, n, warn, fail):
    if n >= fail:
        report.add("doc-length" if rel != "README.md" else "readme-length", "FAIL", rel,
                   "%d lines (limit %d, hard limit %d)" % (n, warn, fail))
    elif n >= warn:
        report.add("doc-length" if rel != "README.md" else "readme-length", "WARN", rel,
                   "%d lines (limit %d)" % (n, warn))


def check_lengths(root, report):
    root = Path(root)
    text = read(root, "README.md", report) if present(root, "README.md") else None
    if text is not None:
        _length(report, "README.md", len(text.splitlines()), README_WARN, README_FAIL)
    docs_map = Path("docs/README.md")
    for rel in ([docs_map] if present(root, docs_map) else []) + human_docs(root):
        text = read(root, rel, report)
        if text is not None:
            _length(report, str(rel), len(text.splitlines()), DOC_WARN, DOC_FAIL)


def _first_paragraph_ok(text):
    body = HTML_COMMENT.sub("", text).split("\n")
    i = 0
    while i < len(body) and not body[i].strip():
        i += 1
    if i >= len(body) or not body[i].startswith("# "):
        return False
    i += 1
    while i < len(body) and not body[i].strip():
        i += 1
    return i < len(body) and not BLOCK_START.match(body[i].lstrip())


def check_first_line(root, report):
    root = Path(root)
    for rel in [Path("README.md"), Path("docs/README.md")] + human_docs(root):
        text = read(root, rel, report) if present(root, rel) else None
        if text is not None and not _first_paragraph_ok(text):
            report.add("first-line", "FAIL", str(rel),
                       "needs an H1 followed by one plain paragraph saying what it is and for whom")


PEOPLE, AGENTS = "## Para personas", "## Para agentes e implementación"


def check_docs_map(root, report):
    root = Path(root)
    rel_map = "docs/README.md"
    if not present(root, rel_map):
        return
    text = read(root, rel_map, report)
    if text is None:
        return
    headings = [l.strip() for l in text.splitlines() if l.startswith("## ")]
    for needed in (PEOPLE, AGENTS):
        if needed not in headings:
            report.add("docs-map", "FAIL", rel_map, "missing section '%s'" % needed)
    linked = set()
    for target in LINK.findall(strip_code(text)):
        path = target.split("#", 1)[0]
        if path and "://" not in path:
            linked.add(os.path.normpath(os.path.join("docs", path)))
    for rel in human_docs(root):
        if os.path.normpath(str(rel)) not in linked:
            report.add("docs-map", "FAIL", rel_map, "does not list %s" % rel)


MD_LINK = re.compile(r"!?\[([^\]]*)\]\([^)]*\)")
SLUG_DROP = re.compile(r"[^\w\- ]", re.UNICODE)


def _no_comments(text):
    # Keep the newline count so line structure stays intact.
    return HTML_COMMENT.sub(lambda m: "\n" * m.group(0).count("\n"), text)


SCHEME = re.compile(r"^[a-zA-Z][a-zA-Z0-9+.-]*:")


def _unfenced_lines(text):
    fenced = False
    for line in _no_comments(text).split("\n"):
        if FENCE.match(line.strip()):
            fenced = not fenced
            continue
        if not fenced:
            yield line


def github_slugs(text):
    seen, slugs = {}, set()
    for line in _unfenced_lines(text):
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*\s*$", line)
        if not m:
            continue
        title = MD_LINK.sub(r"\1", m.group(2))
        base = SLUG_DROP.sub("", title.replace("`", "").lower()).replace(" ", "-")
        n = seen.get(base, 0)
        slugs.add(base if n == 0 else "%s-%d" % (base, n))
        seen[base] = n + 1
    return slugs


def check_links(root, report):
    root = Path(root)
    files = [Path("README.md"), Path("docs/README.md")] + human_docs(root)
    for rel in files:
        if not present(root, rel):
            continue
        text = read(root, rel, report)
        if text is None:
            continue
        for target in LINK.findall(strip_code(_no_comments(text))):
            if target.startswith("<") and target.endswith(">"):
                target = target[1:-1]
            if SCHEME.match(target):
                continue
            path, _, anchor = unquote(target).partition("#")
            if path.startswith("/"):
                dest = root / path.lstrip("/")
            else:
                dest = (root / rel).parent / path if path else root / rel
            if path and not dest.exists():
                report.add("links", "FAIL", str(rel), "broken link %s" % path)
                continue
            if anchor and dest.is_file() and dest.suffix == ".md":
                try:
                    slugs = github_slugs(dest.read_text(encoding="utf-8"))
                except (OSError, UnicodeDecodeError):
                    continue
                if anchor not in slugs:
                    report.add("links", "FAIL", str(rel), "broken anchor #%s" % anchor)


PROCESS_WORDS = [
    re.compile(r"\btask\s+\d+[a-z]?\b", re.I),
    re.compile(r"\bruling", re.I),
    re.compile(r"\bledger\b", re.I),
    re.compile(r"\bfix\s+round", re.I),
    re.compile(r"\bcontroller\b", re.I),
    re.compile(r"\b[a-f0-9]{17}\b", re.I),
    re.compile(r"\b(?:feat|fix|chore|work)/[a-z0-9][\w.-]*", re.I),
]
MAX_MERMAID_BLOCKS, MAX_MERMAID_NODES = 2, 12
LINK_TARGET = re.compile(r"(\[[^\]]*\])\([^)]*\)")


def check_process_words(root, report):
    root = Path(root)
    for rel in [Path("README.md")] + human_docs(root):
        text = read(root, rel, report) if present(root, rel) else None
        if text is None:
            continue
        # Link targets (e.g. docs/README.md) are paths, not process vocabulary.
        text = LINK_TARGET.sub(r"\1", strip_code(_no_comments(text)))
        for rx in PROCESS_WORDS:
            m = rx.search(text)
            if m:
                report.add("process-words", "FAIL", str(rel), "process vocabulary '%s'" % m.group(0))


def _mermaid_blocks(text):
    blocks, cur = [], None
    for line in text.split("\n"):
        s = line.strip()
        if cur is None and s.startswith("```mermaid"):
            cur = []
        elif cur is not None and s.startswith("```"):
            blocks.append("\n".join(cur))
            cur = None
        elif cur is not None:
            cur.append(line)
    return blocks


FLOW_SKIP = {"subgraph", "end", "direction", "classdef", "class", "style", "linkstyle", "click",
             "title", "acctitle", "accdescr"}
SEQ_SKIP = {"note", "loop", "alt", "else", "opt", "par", "and", "rect", "end", "activate", "deactivate",
            "autonumber", "critical", "break", "option", "box", "title", "link", "links", "create", "destroy"}
ARROW = re.compile(r"<?(?:-\.+->?|-{2,}[>ox]?|={2,}>?)")
TEXT_ARROW = re.compile(r"(?:--|==|-\.)[ ]+[^<>]*?[ ]*(?:-->|---|==>|===|\.->|\.-)")
SEQ_MESSAGE = re.compile(r"^(\w+)\s*(?:<<--?>>|--?>>|--?>|--?x|--?\))\s*[+-]?\s*(\w+)\s*:")
SEQ_DECL = re.compile(r"^(?:participant|actor)\s+(\w+)", re.I)


def _blank_shapes(line):
    """Drop quoted strings and the bodies of node shapes so labels cannot be mistaken for ids."""
    line = re.sub(r'"[^"]*"', "", line)
    line = re.sub(r"(?<=\w)>[^\]]*\]", "", line)
    out, depth = [], 0
    for ch in line:
        if ch in "([{":
            depth += 1
        elif ch in ")]}":
            depth = max(0, depth - 1)
        elif depth == 0:
            out.append(ch)
    return "".join(out)


def _diagram_lines(block):
    lines = [l.strip() for l in block.split("\n")]
    lines = [l for l in lines if l]
    if lines and lines[0] == "---":
        end = next((i for i, l in enumerate(lines[1:], 1) if l == "---"), len(lines) - 1)
        lines = lines[end + 1:]
    return [l for l in lines if not l.startswith("%%")]


def _flow_nodes(lines):
    nodes = set()
    for line in lines:
        for stmt in line.split(";"):
            stmt = stmt.strip()
            words = stmt.split(None, 1)
            if not words or words[0].lower().rstrip(":") in FLOW_SKIP:
                continue
            stmt = _blank_shapes(stmt)
            stmt = TEXT_ARROW.sub(" --> ", stmt)
            stmt = re.sub(r"\|[^|]*\|", " ", stmt)
            for part in ARROW.split(stmt):
                for item in part.split("&"):
                    m = re.match(r"\s*(\w+(?:-\w+)*)", item)
                    if m:
                        nodes.add(m.group(1))
    return nodes


def _seq_nodes(lines):
    nodes = set()
    for line in lines:
        first = line.split(None, 1)[0].lower()
        m = SEQ_DECL.match(line)
        if m:
            nodes.add(m.group(1))
        elif first not in SEQ_SKIP:
            m = SEQ_MESSAGE.match(line)
            if m:
                nodes.update(m.groups())
    return nodes


def mermaid_nodes(block):
    """Distinct nodes (flowchart/graph) or participants (sequenceDiagram); 0 for other types."""
    lines = _diagram_lines(block)
    if not lines:
        return 0
    kind = lines[0].split(None, 1)[0].lower()
    if kind in ("flowchart", "graph", "flowchart-elk"):
        return len(_flow_nodes(lines[1:]))
    if kind == "sequencediagram":
        return len(_seq_nodes(lines[1:]))
    return 0


def check_mermaid(root, report):
    root = Path(root)
    for rel in [Path("README.md")] + human_docs(root):
        text = read(root, rel, report) if present(root, rel) else None
        if text is None:
            continue
        blocks = _mermaid_blocks(text)
        if len(blocks) > MAX_MERMAID_BLOCKS:
            report.add("mermaid", "FAIL", str(rel), "%d diagrams (max %d)" % (len(blocks), MAX_MERMAID_BLOCKS))
        for b in blocks:
            n = mermaid_nodes(b)
            if n > MAX_MERMAID_NODES:
                report.add("mermaid", "FAIL", str(rel), "diagram with %d nodes (max %d)" % (n, MAX_MERMAID_NODES))
