"""Lint the per-repository allow files in gitleaks/allow/.

This lints our own reviewed files; it is not a security boundary. Each file may contain only blank lines,
`#` comments and `[[allowlists]]` tables with single-line `key = value` entries whose keys are among the
allowed set. Every table must also be narrow: `paths` anchored with `^...$`, at least one of `commits`,
`regexes` or `targetRules`, and `condition = "AND"` when `paths` is combined with `commits`, `regexes` or
`stopwords`. Paths and regexes may not be wildcards (`.*`, `.+`). Every key line must parse on its own
as exactly one allowed key, so no value spans lines. `[extend]`, `[[rules]]`, `[allowlist]`, other tables
and top-level keys are errors.
Usage: python3 -I gitleaks/check_allow.py [directory]     lint a directory (default: gitleaks/allow)
       python3 -I gitleaks/check_allow.py --list [dir]    print the file names the linter would lint
"""
import sys
import tomllib
from pathlib import Path

KEYS = ("description", "condition", "commits", "paths", "regexes", "regexTarget", "stopwords", "targetRules")
WILDCARD_REGEXES = {"", ".*", ".+", "^.*$", "^.+$"}


def line_error(line):
    """A key line must parse on its own into exactly one allowed key, so no value can span lines."""
    try:
        data = tomllib.loads(line)
    except tomllib.TOMLDecodeError as error:
        return f"line does not parse on its own: {error}"
    if len(data) != 1 or next(iter(data)) not in KEYS:
        return "not exactly one allowed key"
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
            elif ".*" in path or ".+" in path:
                problems.append(f"path pattern with a wildcard (.* or .+): {path!r}")
    for regex in table.get("regexes", []):
        if regex in WILDCARD_REGEXES:
            problems.append(f"regex matches everything or nothing: {regex!r}")
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
        elif line_error(line):
            errors.append(f"{path.name}:{number}: {line_error(line)}: {line[:60]}")
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
