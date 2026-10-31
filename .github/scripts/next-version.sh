#!/usr/bin/env bash
# Print the next semantic version tag.
#   usage: next-version.sh <latest-tag-or-empty> <major|minor|patch>
# A missing latest tag starts from v0.0.0. Only plain vX.Y.Z tags are understood.
set -euo pipefail

latest="${1:-}"
bump="${2:-patch}"

if [ -z "$latest" ]; then
  latest="v0.0.0"
fi
if [[ ! "$latest" =~ ^v([0-9]+)\.([0-9]+)\.([0-9]+)$ ]]; then
  echo "Latest tag '$latest' is not in vX.Y.Z form" >&2
  exit 1
fi
major="${BASH_REMATCH[1]}"
minor="${BASH_REMATCH[2]}"
patch="${BASH_REMATCH[3]}"

case "$bump" in
  major) major=$((major + 1)); minor=0; patch=0 ;;
  minor) minor=$((minor + 1)); patch=0 ;;
  patch) patch=$((patch + 1)) ;;
  *) echo "Unknown bump '$bump' (expected major, minor or patch)" >&2; exit 1 ;;
esac

echo "v${major}.${minor}.${patch}"
