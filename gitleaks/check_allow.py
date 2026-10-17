"""Lint the per-repository allow files in gitleaks/allow/.

This lints our own reviewed files; it is not a security boundary. Each file may contain only blank lines,
`#` comments and `[[allowlists]]` tables with single-line `key = value` entries whose keys are among the
allowed set. Every table must also be narrow: `paths` anchored with `^...$`, at least one of `commits`,
`regexes` or `targetRules`, and `condition = "AND"` when `paths` is combined with `commits`, `regexes` or
`stopwords`. `[extend]`, `[[rules]]`, `[allowlist]`, other tables, top-level keys, triple-double-quoted
strings and backslashes outside literal strings are errors.
Usage: python3 -I gitleaks/check_allow.py [directory]     lint a directory (default: gitleaks/allow)
       python3 -I gitleaks/check_allow.py --list [dir]    print the file names the linter would lint
"""
import re
import sys
import tomllib
from pathlib import Path

KEYS = ("description", "condition", "commits", "paths", "regexes", "regexTarget", "stopwords", "targetRules")
KEY_LINE = re.compile(r"^(" + "|".join(KEYS) + r")\s*=\s*\S")
LITERAL = re.compile(r"'''.*?'''")


def line_errors(line):
    if '"""' in line:
        return "triple-double-quoted strings are not allowed"
    if line.count("'''") % 2:
        return "unbalanced ''' literal string"
    if "\\" in LITERAL.sub("", line):
        return "backslashes are only allowed inside ''' literal strings"
    return None


def table_errors(table):
    problems = []
    paths = table.get("paths")
    if not isinstance(paths, list) or not paths:
        problems.append("missing paths")
    else:
        for path in paths:
            if not (isinstance(path, str) and path.startswith("^") and path.endswith("$")):
                problems.append(f"path not anchored with ^...$: {path!r}")
    if not any(table.get(key) for key in ("commits", "regexes", "targetRules")):
        problems.append("needs at least one of commits, regexes or targetRules")
    if any(table.get(key) for key in ("commits", "regexes", "stopwords")) and table.get("condition") != "AND":
        problems.append('condition = "AND" is required when paths is combined with commits, regexes or stopwords')
    return problems


def lint(path):
    errors = []
    in_table = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[allowlists]]":
            in_table = True
            continue
        if not in_table:
            errors.append(f"{path.name}:{number}: only comments may precede the first [[allowlists]] table")
        elif not KEY_LINE.match(line):
            errors.append(f"{path.name}:{number}: not an allowed line: {line[:60]}")
        elif line_errors(line):
            errors.append(f"{path.name}:{number}: {line_errors(line)}")
    if errors:
        return errors
    try:
        data = tomllib.loads(path.read_text(encoding="utf-8"))
    except tomllib.TOMLDecodeError as error:
        return [f"{path.name}: invalid TOML: {error}"]
    tables = data.get("allowlists")
    if set(data) != {"allowlists"} or not isinstance(tables, list) or not tables:
        return [f"{path.name}: expected only [[allowlists]] tables"]
    for index, table in enumerate(tables, 1):
        errors += [f"{path.name}: table {index}: {problem}" for problem in table_errors(table)]
    return errors


def main(argv):
    args = argv[1:]
    list_only = bool(args) and args[0] == "--list"
    if list_only:
        args = args[1:]
    directory = Path(args[0]) if args else Path(__file__).resolve().parent / "allow"
    files = sorted(directory.glob("*.toml"))
    if list_only:
        print("\n".join(path.name for path in files))
        return 0
    if not files:
        print(f"no allow files in {directory}", file=sys.stderr)
        return 1
    errors = [error for path in files for error in lint(path)]
    for error in errors:
        print(error, file=sys.stderr)
    if not errors:
        print(f"OK: {len(files)} allow file(s)")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
