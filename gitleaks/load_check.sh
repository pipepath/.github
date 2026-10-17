#!/usr/bin/env bash
# Loads the composed central configurations into the pinned gitleaks image against an empty directory, so a
# malformed file fails here instead of in the scan of another repository. The composition is the same one the
# reusable workflow does: base.toml, then base.toml + a newline + each allow file.
# Usage: gitleaks/load_check.sh (from the repository root; needs docker)
set -euo pipefail
export LC_ALL=C
image=ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT
mkdir "$work/empty"

load() {
  docker run --rm -v "$work/empty:/empty:ro" -v "$work/gitleaks.toml:/central/gitleaks.toml:ro" "$image" \
    dir /empty --config /central/gitleaks.toml --no-banner --redact
}

# The loader must see exactly the files the linter lints (a dotfile such as allow/.github.toml included).
shopt -s dotglob nullglob
files=(gitleaks/allow/*.toml)
if [ "$(printf '%s\n' "${files[@]##*/}" | LC_ALL=C sort)" != "$(python3 -I gitleaks/check_allow.py --list | LC_ALL=C sort)" ]; then
  echo "load_check.sh and check_allow.py see different allow files" >&2
  exit 1
fi

{ cat gitleaks/base.toml; printf '\n'; } > "$work/gitleaks.toml"
echo "load: base.toml"
load
for allow in "${files[@]}"; do
  { cat gitleaks/base.toml; printf '\n'; cat "$allow"; printf '\n'; } > "$work/gitleaks.toml"
  echo "load: base.toml + $allow"
  load
done
