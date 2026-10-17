"""Lint the per-repository allow files in gitleaks/allow/.

Each file may contain only blank lines, `#` comments and `[[allowlists]]` tables whose keys are among the
allowed set. Anything else (`[extend]`, `[[rules]]`, `[allowlist]`, other tables, top-level keys, multi-line
values) is an error: the central scan composes base.toml with these files, so an allow file must never be able
to change the rules or the extension. Usage: python3 -I gitleaks/check_allow.py [directory]
"""
import re
import sys
from pathlib import Path

KEYS = ("description", "condition", "commits", "paths", "regexes", "regexTarget", "stopwords", "targetRules")
KEY_LINE = re.compile(r"^(" + "|".join(KEYS) + r")\s*=\s*\S")


def lint(path):
    errors = []
    in_table = False
    for number, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        line = raw.strip()
        if not line or line.startswith("#"):
            continue
        if line == "[[allowlists]]":
            in_table = True
        elif not in_table:
            errors.append(f"{path}:{number}: only comments may precede the first [[allowlists]] table")
        elif KEY_LINE.match(line):
            if line.count("'''") % 2 or line.count('"""') % 2:
                errors.append(f"{path}:{number}: multi-line values are not allowed")
        else:
            errors.append(f"{path}:{number}: not an allowed line: {line[:60]}")
    return errors


def main(argv):
    directory = Path(argv[1]) if len(argv) > 1 else Path(__file__).resolve().parent / "allow"
    files = sorted(directory.glob("*.toml"))
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
