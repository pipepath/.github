"""Caller `.gitleaks.toml` rules shared by the `gitleaks-allowlist` check and `gitleaks_config.py`.

The file is untrusted input. It is only parsed (stdlib `tomllib`), never executed, and the config the scan uses
is rebuilt from the entries this module accepts, serialized by `render_entry`; the caller's text never reaches
gitleaks. gitleaks reads TOML with a different parser (Go, viper: case-insensitive keys and more), so the
accepted shape is a closed list compared case-sensitively and anything else is a problem: a caller cannot hide
content from this check that gitleaks would honor. Without `tomllib` (Python < 3.11) nothing can be validated,
so the check fails closed and the merge keeps only the base config.

Messages never echo caller strings (the report is printed to a CI log where `::` lines are workflow commands).
"""

import re
import string
from pathlib import Path

try:
    import tomllib
except ImportError:  # pragma: no cover - exercised by patching `tomllib` to None
    tomllib = None

CONFIG = ".gitleaks.toml"
LIST_KEYS = ("commits", "paths", "regexes", "stopwords", "targetRules")
STRING_KEYS = ("description", "condition", "regexTarget")
CARRIED = ("description", "condition", "commits", "paths", "regexes", "regexTarget", "stopwords", "targetRules")
SCOPE_KEYS = ("commits", "paths", "regexes", "stopwords")
REGEX_TARGETS = ("match", "line", "secret")
MIN_STOPWORD = 3
PROBES = [""] + [c * n for c in string.printable for n in (1, 2, 3)]


def toml_string(value):
    """A TOML basic string that round-trips through tomllib."""
    out = []
    for ch in value:
        if ch == '"':
            out.append('\\"')
        elif ch == "\\":
            out.append("\\\\")
        elif ord(ch) < 0x20 or ord(ch) == 0x7F:
            out.append("\\u%04x" % ord(ch))
        else:
            out.append(ch)
    return '"%s"' % "".join(out)


def render_entry(entry):
    """One `[[allowlists]]` table with only the carried keys (values already validated)."""
    lines = ["[[allowlists]]"]
    for key in CARRIED:
        if key not in entry:
            continue
        value = entry[key]
        if isinstance(value, list):
            lines.append("%s = [%s]" % (key, ", ".join(toml_string(v) for v in value)))
        else:
            lines.append("%s = %s" % (key, toml_string(value)))
    return "\n".join(lines) + "\n"


ESCAPABLE = frozenset(".-+()[]{}*?|^$\\")
LITERAL_FORBIDDEN = frozenset("\\.^$|?*+()[]{}")


def _path_problem(pattern):
    """A path entry is one exact file: `^`, literal characters, `$`. The only backslash escapes allowed are
    escaped regex metacharacters; classes, groups, alternation, quantifiers, `.`, flags and other escapes
    are rejected, so an entry can never match more than the single file it names."""
    if not pattern.startswith("^") or len(pattern) < 3 or not pattern.endswith("$"):
        return "a path pattern must be ^ + the literal file path + $"
    body, i = pattern[1:-1], 0
    while i < len(body):
        c = body[i]
        if c == "\\":
            if i + 1 >= len(body) or body[i + 1] not in ESCAPABLE:
                return "a path pattern uses a backslash escape other than an escaped metacharacter"
            i += 2
        elif c in LITERAL_FORBIDDEN:
            return "a path pattern is not an exact file path (only literals and escaped metacharacters)"
        else:
            i += 1
    return None


def _regex_problem(pattern):
    if not pattern:
        return "a regex is empty"
    try:
        rx = re.compile(pattern)
        broad = any(rx.search(p) for p in PROBES)
    except (re.error, RecursionError, OverflowError):
        return "a regex cannot be analyzed (it must compile and be specific)"
    if broad:
        return "a regex matches the empty string or a single repeated character, so it is too broad"
    return None


def entry_problem(entry):
    """None when the allowlist entry is acceptable, else a short reason (never echoes caller strings)."""
    if not isinstance(entry, dict):
        return "the entry is not a table"
    if any(k not in CARRIED for k in entry):
        return "the entry has a key this check does not model (keys are case-sensitive)"
    for key in LIST_KEYS:
        if key in entry and not (isinstance(entry[key], list) and all(isinstance(v, str) for v in entry[key])):
            return "%s must be an array of strings" % key
    for key in STRING_KEYS:
        if key in entry and not isinstance(entry[key], str):
            return "%s must be a string" % key
    if "regexTarget" in entry and entry["regexTarget"] not in REGEX_TARGETS:
        return "regexTarget must be match, line or secret"
    paths = entry.get("paths") or []
    if not paths:
        return "missing paths (every entry must be scoped to anchored paths)"
    for p in paths:
        problem = _path_problem(p)
        if problem:
            return problem
    for r in entry.get("regexes") or []:
        problem = _regex_problem(r)
        if problem:
            return problem
    if any(len(w) < MIN_STOPWORD for w in entry.get("stopwords") or []):
        return "a stopword is shorter than %d characters" % MIN_STOPWORD
    if not any(entry.get(k) for k in ("commits", "regexes", "targetRules")):
        return "paths alone is too broad: add commits, regexes or targetRules"
    if "condition" in entry and entry["condition"] != "AND":
        return 'condition may only be exactly "AND"'
    if sum(1 for k in SCOPE_KEYS if entry.get(k)) >= 2 and "condition" not in entry:
        return 'two or more of commits, paths, regexes, stopwords need condition = "AND"'
    return None


def load(root):
    """(config dict | None, problem | None). A problem means the caller config must not be honored."""
    path = Path(root) / CONFIG
    if path.is_symlink():
        return None, "%s is a symbolic link" % CONFIG
    if not path.exists():
        return None, None
    if tomllib is None:
        return None, "the config cannot be checked: tomllib needs Python 3.11 or newer"
    try:
        with open(path, "rb") as fh:
            return tomllib.load(fh), None
    except (OSError, UnicodeDecodeError, tomllib.TOMLDecodeError) as e:
        return None, "%s cannot be read as TOML (%s)" % (CONFIG, type(e).__name__)


def config_problems(cfg):
    """Every reason the parsed config is not acceptable (empty list = acceptable). Modeled: `title`,
    `minVersion` (strings), `[extend]` with only `useDefault = true`, and `[[allowlists]]`."""
    out = []
    for key in cfg:
        if key == "rules":
            out.append("[[rules]] are not allowed (the central config owns every rule)")
        elif key == "allowlist":
            out.append("the legacy [allowlist] table is not allowed; use [[allowlists]]")
        elif key not in ("title", "minVersion", "extend", "allowlists"):
            out.append("the config has a top-level key this check does not model (keys are case-sensitive)")
    for key in ("title", "minVersion"):
        if key in cfg and not isinstance(cfg[key], str):
            out.append("%s must be a string" % key)
    ext = cfg.get("extend")
    if "extend" in cfg and not (isinstance(ext, dict) and list(ext) == ["useDefault"] and ext["useDefault"] is True):
        out.append("[extend] must contain only useDefault = true")
    lists = cfg.get("allowlists", [])
    if not isinstance(lists, list):
        out.append("allowlists must be an array of tables")
    else:
        for i, entry in enumerate(lists):
            reason = entry_problem(entry)
            if reason:
                out.append("allowlists #%d: %s" % (i + 1, reason))
    return out


def check_gitleaks_allowlist(root, report):
    cfg, problem = load(root)
    if problem:
        report.add("gitleaks-allowlist", "FAIL", CONFIG, problem)
        return
    if cfg is None:
        return
    for reason in config_problems(cfg):
        report.add("gitleaks-allowlist", "FAIL", CONFIG, reason)
