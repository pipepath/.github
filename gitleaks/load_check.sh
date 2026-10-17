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

cp gitleaks/base.toml "$work/gitleaks.toml"
echo "load: base.toml"
load
for allow in gitleaks/allow/*.toml; do
  { cat gitleaks/base.toml; printf '\n'; cat "$allow"; printf '\n'; } > "$work/gitleaks.toml"
  echo "load: base.toml + $allow"
  load
done
