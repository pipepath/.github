#!/usr/bin/env python3
"""Pipepath repo-standards verifier (spec 2026-10-17 §3.3). Stdlib only.

Exit codes: 0 clean (warnings allowed), 1 findings, 2 usage error.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from standards import ci, docs  # noqa: E402
from standards.report import Report  # noqa: E402

CHECKS = [docs.check_files, docs.check_lengths, docs.check_first_line, docs.check_docs_map, docs.check_links,
          docs.check_process_words, docs.check_mermaid, ci.check_workflows, ci.check_pr_template,
          ci.check_gitleaks_local]


def run(root, version=None, repo_private=None, central_gitleaks=None, repo_name=None):
    """Only the exact string "true" selects the private rules; anything else (including None) is public."""
    report = Report()
    public = repo_private != "true"
    if repo_private is not None and repo_private not in ("true", "false"):
        report.add("visibility", "WARN", ".", "--repo-private value %r is neither 'true' nor 'false'; "
                   "the repository was treated as public" % repo_private)
    for check in CHECKS:
        if check is ci.check_workflows:
            check(root, report, public=public)
        elif check is ci.check_gitleaks_local:
            check(root, report, central_dir=central_gitleaks, repo_name=repo_name)
        else:
            check(root, report)
    ci.check_skill_version(root, report, version)
    return report


def main(argv=None):
    ap = argparse.ArgumentParser(description="Verify a repository against the Pipepath repo standard.",
                                 allow_abbrev=False)
    ap.add_argument("root")
    ap.add_argument("--version", default=None, help="expected repo-standards VERSION")
    ap.add_argument("--repo-private", default=None, metavar="VALUE",
                    help="the repository's visibility: only the exact value 'true' selects the private rules; "
                         "anything else (or no flag) selects the public rules, where every job's runs-on must be "
                         "exactly the canonical expression")
    ap.add_argument("--central-gitleaks", default=None, metavar="DIR",
                    help="checkout of pipepath/.github's gitleaks/ directory (for the gitleaks-local check)")
    ap.add_argument("--repo-name", default=None, metavar="NAME",
                    help="repository name, used to look up DIR/allow/NAME.toml")
    ap.add_argument("--format", choices=["text", "json"], default="text")
    args = ap.parse_args(argv)
    root = Path(args.root)
    if not root.is_dir():
        print("repo-standards: not a directory: %s" % root)
        return 2
    report = run(root, args.version, args.repo_private, args.central_gitleaks, args.repo_name)
    print(report.to_json() if args.format == "json" else report.to_text())
    return report.exit_code()


if __name__ == "__main__":
    sys.exit(main())
