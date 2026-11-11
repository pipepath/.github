"""Catalog entry check. A repository describes itself in `catalog.mdoc` and/or `catalog/*.mdoc`: Markdoc files
that open with a frontmatter block. This module checks only the minimal, mechanical contract (the frontmatter
is well formed and the required fields are present with valid enums); the full validation belongs to the
catalog build."""

import os
import re

from standards.ci import REPO_NAME

# Phase switch: False reports a missing entry as a warning, True as a failure.
CATALOG_REQUIRED = False

KINDS = ("api", "service", "site", "package", "resource", "doc")
STATUSES = ("production", "building", "experimental", "retired")
REQUIRED_FIELDS = ("name", "kind", "summary", "product", "status", "owner", "repo")
FORBIDDEN_FIELDS = ("used_by",)
EXEMPT_NAMES = (".github", "workspaces-hub")
EXEMPT_SUFFIX = "-workspace"

KEY_LINE = re.compile(r"([a-z_][a-z0-9_]*):(?:[ \t]+(.*))?")
QUOTED = re.compile(r"""("[^"]*"|'[^']*')[ \t]*(?:#.*)?""")
BLOCK_SCALAR = re.compile(r"[|>][+-]?[0-9]?[+-]?")
MISSING_MESSAGE = "no catalog entry (catalog.mdoc or catalog/*.mdoc); it will become required"


def entry_files(root):
    """`catalog.mdoc` (even as a symlink) followed by the sorted `catalog/*.mdoc`; nothing else."""
    files = []
    single = root / "catalog.mdoc"
    if os.path.lexists(single):
        files.append(single)
    files.extend(sorted((root / "catalog").glob("*.mdoc")))
    return files


def _scalar(raw):
    raw = raw.strip()
    quoted = QUOTED.fullmatch(raw)
    if quoted:
        return quoted.group(1)[1:-1]
    if raw.startswith("#"):
        return ""
    match = re.search(r"[ \t]#", raw)
    return (raw[:match.start()] if match else raw).strip()


def parse_frontmatter(text):
    """Top-level keys of the frontmatter: the scalar value (no quotes, no trailing comment), or None when the
    key opens a block. Also returns the list of problems found."""
    problems = []
    values = {}
    lines = text.splitlines()
    if not lines or lines[0].rstrip() != "---":
        return values, ["frontmatter must start with '---' on the first line"]
    end = None
    for index in range(1, len(lines)):
        if lines[index].rstrip() == "---":
            end = index
            break
    if end is None:
        return values, ["frontmatter is not closed with '---'"]
    current = None
    has_children = set()
    for number, line in enumerate(lines[1:end], start=2):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        indent = line[:len(line) - len(line.lstrip(" \t"))]
        if "\t" in indent:
            problems.append("line %d: tab in indentation" % number)
            continue
        if indent or (line.startswith("- ") or line.rstrip() == "-"):
            if current is None:
                problems.append("line %d: indented line without a key" % number)
            else:
                has_children.add(current)
            continue
        match = KEY_LINE.fullmatch(line.rstrip())
        if match is None:
            problems.append("line %d: expected 'key: value'" % number)
            current = None
            continue
        key = match.group(1)
        current = key
        if key in values:
            problems.append("line %d: duplicate key '%s'" % (number, key))
            current = None
            continue
        values[key] = _scalar(match.group(2) or "")
    for key, value in values.items():
        if value == "" and key in has_children:
            values[key] = None
        elif value is not None and BLOCK_SCALAR.fullmatch(value) and key not in has_children:
            values[key] = ""  # a block scalar indicator with no continuation line is empty
    return values, problems


def _read(path):
    if path.is_symlink() or not path.is_file():
        return None, "must be a regular file"
    try:
        return path.read_bytes().decode("utf-8"), None
    except UnicodeDecodeError:
        return None, "must be valid UTF-8"


def _problems(values):
    found = []
    for field in REQUIRED_FIELDS:
        if field not in values:
            found.append("missing required field '%s'" % field)
        elif values[field] is None:
            found.append("field '%s' must be a single-line value, not a block" % field)
        elif values[field] == "":
            found.append("required field '%s' is empty" % field)
    kind = values.get("kind")
    if isinstance(kind, str) and kind and kind not in KINDS:
        found.append("kind '%s' is not one of: %s" % (kind, ", ".join(KINDS)))
    status = values.get("status")
    if isinstance(status, str) and status and status not in STATUSES:
        found.append("status '%s' is not one of: %s" % (status, ", ".join(STATUSES)))
    if kind == "api" and not values.get("openapi"):
        found.append("missing required field 'openapi' (kind is api)")
    for field in FORBIDDEN_FIELDS:
        if field in values:
            found.append("field '%s' is not allowed; it is computed" % field)
    return found


def check_catalog(root, report, repo_name=None, required=None):
    if required is None:
        required = CATALOG_REQUIRED
    if repo_name is not None and (repo_name in EXEMPT_NAMES or repo_name.endswith(EXEMPT_SUFFIX)):
        return
    rules = root / "org-rules"
    if rules.is_dir() and not rules.is_symlink():
        return
    files = entry_files(root)
    if not files:
        valid = (repo_name is not None and REPO_NAME.fullmatch(repo_name) is not None
                 and repo_name not in (".", ".."))
        if valid:
            report.add("catalog", "FAIL" if required else "WARN", ".", MISSING_MESSAGE)
        return
    for path in files:
        rel = path.relative_to(root).as_posix()
        text, problem = _read(path)
        if problem:
            report.add("catalog", "FAIL", rel, "%s: %s" % (rel, problem))
            continue
        values, problems = parse_frontmatter(text)
        if not problems:
            problems = _problems(values)
        for problem in problems:
            report.add("catalog", "FAIL", rel, "%s: %s" % (rel, problem))
