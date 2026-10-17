#!/usr/bin/env python3
"""Print the central gitleaks config for a caller repository (stdlib only).

Usage: python3 -I gitleaks_config.py <caller-root>

The output always starts from the base config (`gitleaks.toml`, next to this file). The caller's root
`.gitleaks.toml` contributes its `[[allowlists]]` entries, re-serialized by our code, only when the whole file
passes the `gitleaks-allowlist` rule; if anything in it fails, nothing is carried (fail closed). Notices go
to stderr and never echo caller strings. A caller config that is absent, unreadable or invalid yields the base config alone, and the
exit code stays 0 (the central scan must still run). Exit 2: usage error or missing base config.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from standards import gitleaks  # noqa: E402

BASE = Path(__file__).resolve().parent / "gitleaks.toml"


def notice(message):
    print("gitleaks-config: %s" % message, file=sys.stderr)


def merge(root, base_text):
    out = base_text if base_text.endswith("\n") else base_text + "\n"
    if gitleaks.tomllib is None:
        notice("tomllib is not available (Python 3.11 or newer needed); using the base config only")
        return out
    cfg, problem = gitleaks.load(root)
    if problem:
        notice("%s; using the base config only" % problem)
        return out
    if cfg is None:
        notice("no %s in the caller; using the base config only" % gitleaks.CONFIG)
        return out
    problems = gitleaks.config_problems(cfg)
    if problems:
        for reason in problems:
            notice(reason)
        notice("the caller config is not acceptable; using the base config only (carrying nothing is fail-closed)")
        return out
    for entry in cfg.get("allowlists", []):
        out += "\n" + gitleaks.render_entry(entry)
    return out


def main(argv=None):
    ap = argparse.ArgumentParser(description="Print the merged central gitleaks config.")
    ap.add_argument("root")
    args = ap.parse_args(argv)
    try:
        base_text = BASE.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        notice("cannot read the base config (%s)" % type(e).__name__)
        return 2
    sys.stdout.write(merge(Path(args.root), base_text))
    return 0


if __name__ == "__main__":
    sys.exit(main())
