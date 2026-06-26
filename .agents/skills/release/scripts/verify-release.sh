#!/usr/bin/env bash
# verify-release.sh — verify a published nanoPyCodeAgent release.
#
# Against the OFFICIAL PyPI index (bypassing any local mirror lag) it checks:
#   1. the version is present on PyPI
#   2. a GitHub Release exists for the tag with wheel + sdist assets
#   3. `uvx ...@VERSION` runs the console entry point (smoke test)
#
# Usage: verify-release.sh <version|vVERSION>   e.g. verify-release.sh 0.1.1
#
# Smoke test runs the entry point with no args (currently side-effect-free).
# If the entry point ever gains required args/interaction, adjust step 3.
set -euo pipefail

PACKAGE="nanoPyCodeAgent"
PYPI_JSON="https://pypi.org/pypi/${PACKAGE}/json"
PYPI_INDEX="https://pypi.org/simple/"
POLL_TIMEOUT="${VERIFY_TIMEOUT:-300}"   # seconds budget per polling stage
POLL_INTERVAL="${VERIFY_INTERVAL:-15}"  # seconds between polls

usage() {
  cat <<'EOF'
Usage: verify-release.sh <version|vVERSION>

Verifies a published release against official PyPI + GitHub Release:
  1. version present on PyPI (pinned to pypi.org, ignores mirrors)
  2. GitHub Release for the tag has wheel + sdist assets
  3. uvx smoke test runs the published artifact

Env overrides:
  VERIFY_TIMEOUT   seconds to wait per polling stage (default 300)
  VERIFY_INTERVAL  seconds between polls (default 15)
EOF
}

if [[ $# -ne 1 ]]; then usage; exit 1; fi
if [[ "$1" == "-h" || "$1" == "--help" ]]; then usage; exit 0; fi

version="${1#v}"     # strip leading v -> 0.1.1
tag="v${version}"    # normalized tag -> v0.1.1

log()  { printf '\n=== %s ===\n' "$*"; }
fail() { printf 'ERROR: %s\n' "$*" >&2; exit 1; }

# 1. PyPI presence (poll, pinned to official index) -----------------------
log "Checking PyPI for ${PACKAGE} ${version}"
deadline=$(( $(date +%s) + POLL_TIMEOUT ))
until curl -fsSL "$PYPI_JSON" | grep -q "\"${version}\""; do
  (( $(date +%s) >= deadline )) && fail "version ${version} not on PyPI after ${POLL_TIMEOUT}s"
  printf 'not on PyPI yet; retrying in %ss...\n' "$POLL_INTERVAL"; sleep "$POLL_INTERVAL"
done
printf 'OK: %s %s is on PyPI\n' "$PACKAGE" "$version"

# 2. GitHub Release + assets ----------------------------------------------
log "Checking GitHub Release ${tag}"
gh release view "$tag" >/dev/null 2>&1 || fail "no GitHub Release for ${tag}"
assets="$(gh release view "$tag" --json assets --jq '.assets[].name')"
grep -q '\.whl$'     <<<"$assets" || fail "Release ${tag} missing a wheel (.whl) asset"
grep -q '\.tar\.gz$' <<<"$assets" || fail "Release ${tag} missing an sdist (.tar.gz) asset"
printf 'OK: GitHub Release %s has wheel + sdist\n' "$tag"

# 3. uvx smoke test (official index, with retries) ------------------------
log "Smoke-testing uvx ${PACKAGE}@${version}"
deadline=$(( $(date +%s) + POLL_TIMEOUT ))
until uvx --index "$PYPI_INDEX" --from "${PACKAGE}@${version}" "$PACKAGE" >/dev/null 2>&1; do
  (( $(date +%s) >= deadline )) && fail "uvx smoke test failed for ${PACKAGE}@${version} after ${POLL_TIMEOUT}s"
  printf 'uvx not ready (index propagation?); retrying in %ss...\n' "$POLL_INTERVAL"; sleep "$POLL_INTERVAL"
done
printf 'OK: uvx smoke test passed for %s@%s\n' "$PACKAGE" "$version"

log "Release ${tag} verified ✔"
