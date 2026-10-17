#!/usr/bin/env bash
# Regression test of the spawn-control allowlist: a JWT with the fixture header in the fixture path is
# allowed, while a JWT with another header in that path, or any JWT in another path, is still reported.
# Tokens are built at run time; no token-shaped literal is stored in the repository.
# Usage: bash gitleaks/tests/scan_anchor.sh (from the repository root; needs docker)
# ALLOW_FILE overrides the allow file under test (used to check that the test fails without the anchor).
set -euo pipefail
export LC_ALL=C
image=ghcr.io/gitleaks/gitleaks:v8.30.1@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f
allow="${ALLOW_FILE:-gitleaks/allow/spawn-control.toml}"
root="$PWD"
work="$(mktemp -d)"
trap 'rm -rf "$work"' EXIT

# Same composition as the gitleaks job of the reusable workflow, written to a fresh file.
mkdir "$work/cfg"
{ cat "$root/gitleaks/base.toml"; printf '\n'; cat "$root/$allow"; printf '\n'; } > "$work/cfg/gitleaks.toml"
cp "$root/gitleaks/empty.gitleaksignore" "$work/cfg/empty.gitleaksignore"

b64url() { base64 | tr '+/' '-_' | tr -d '=\n'; }

# token <kid>: a JWT-shaped string with random payload and signature segments.
token() {
  local header payload sig
  header="$(printf '{"alg":"EdDSA","typ":"JWT","kid":"%s"}' "$1" | b64url)"
  payload="$(printf '{"sub":"%s","aud":"test"}' "$(head -c 24 /dev/urandom | od -An -tx1 | tr -d ' \n')" | b64url)"
  sig="$(head -c 48 /dev/urandom | b64url)"
  printf '%s.%s.%s' "$header" "$payload" "$sig"
}

status=0
# scan <label> <kid> <path> <expect: clean|jwt>
scan() {
  local label="$1" kid="$2" path="$3" expect="$4" repo out rc=0
  repo="$(mktemp -d "$work/repo.XXXXXX")"
  out="$(mktemp -d "$work/out.XXXXXX")"
  git -C "$repo" init -q
  mkdir -p "$repo/$(dirname "$path")"
  printf '{"token":"%s"}\n' "$(token "$kid")" > "$repo/$path"
  git -C "$repo" add "$path"
  git -C "$repo" -c user.name=test -c user.email=test@example.invalid -c commit.gpgsign=false commit -q -m fixture
  rm -rf "$repo/.gitleaksignore"
  docker run --rm -v "$repo:/repo" -v "$work/cfg:/central:ro" -v "$out:/out" "$image" \
    git /repo --config /central/gitleaks.toml --gitleaks-ignore-path /central/empty.gitleaksignore \
    --ignore-gitleaks-allow --log-opts="--full-history --all" --redact --exit-code 7 \
    --report-format json --report-path /out/report.json --no-banner >/dev/null 2>&1 || rc=$?
  if [ "$expect" = clean ]; then
    if [ "$rc" -eq 0 ]; then echo "ok: $label: no finding"; else echo "FAIL: $label: exit $rc, expected no finding" >&2; status=1; fi
  else
    if [ "$rc" -eq 7 ] && grep -q '"RuleID": *"jwt"' "$out/report.json"; then
      echo "ok: $label: jwt finding"
    else
      echo "FAIL: $label: exit $rc, expected a jwt finding" >&2; status=1
    fi
  fi
}

scan "fixture-1 header in the fixture path" fixture-1 contract/fixtures/control/ticket-response.json clean
scan "kid other in the fixture path" other contract/fixtures/control/ticket-response.json jwt
scan "kid other in another path" other contract/fixtures/control/other.json jwt
scan "fixture-1 header in another path" fixture-1 contract/fixtures/control/other.json jwt
exit "$status"
