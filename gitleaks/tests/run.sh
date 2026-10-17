#!/usr/bin/env bash
# Regression test of check_allow.py: every real allow file must pass and every crafted file in tests/bad/
# must fail. Usage: bash gitleaks/tests/run.sh (from the repository root)
set -euo pipefail
python3 -I gitleaks/check_allow.py
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
status=0
for bad in gitleaks/tests/bad/*.toml; do
  rm -rf "$work/dir"; mkdir "$work/dir"; cp "$bad" "$work/dir/"
  if python3 -I gitleaks/check_allow.py "$work/dir" >/dev/null 2>&1; then
    echo "FAIL: the linter accepted $bad" >&2
    status=1
  else
    echo "ok: rejected $bad"
  fi
done
exit "$status"
