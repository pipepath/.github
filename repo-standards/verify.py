#!/usr/bin/env python3
"""Pipepath repo-standards verifier (spec 2026-10-17 §3.3). Stdlib only.

Exit codes: 0 clean (warnings allowed), 1 findings, 2 usage error.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from standards import ci, docs, gitleaks  # noqa: E402
from standards.report import Report  # noqa: E402

CHECKS = [docs.check_files, docs.check_lengths, docs.check_first_line, docs.check_docs_map, docs.check_links,
          docs.check_process_words, docs.check_mermaid, ci.check_workflows, ci.check_pr_template,
          gitleaks.check_gitleaks_allowlist]


def run(root, version=None):
    report = Report()
    for check in CHECKS:
        check(root, report)
    ci.check_skill_version(root, report, version)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a repository against the Pipepath repo standard.")
    ap.add_argument("root")
    ap.add_argument("--version", default=None, help="expected repo-standards VERSION")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("repo-standards: not a directory: %s" % root)
        return 2
    report = run(root, args.version)
    print(report.to_json() if args.format == "json" else report.to_text())
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
