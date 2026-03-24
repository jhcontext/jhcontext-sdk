#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# ── Usage ─────────────────────────────────────────────────────────
usage() {
    echo "Usage: $0 [patch|minor|major|<version>] [-m <description>]"
    echo ""
    echo "  patch              bump patch version (default)"
    echo "  minor              bump minor version"
    echo "  major              bump major version"
    echo "  <x.y.z>            set custom version"
    echo "  -m <description>   release description (default: 'release vX.Y.Z')"
    echo ""
    echo "Examples:"
    echo "  $0                 # interactive mode"
    echo "  $0 patch           # auto patch bump"
    echo "  $0 minor -m 'new feature'"
    exit 0
}

[[ "${1:-}" == "-h" || "${1:-}" == "--help" ]] && usage

# ── Get current version ────────────────────────────────────────────
CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

# ── Auto-increment options ─────────────────────────────────────────
NEXT_PATCH="$MAJOR.$MINOR.$((PATCH + 1))"
NEXT_MINOR="$MAJOR.$((MINOR + 1)).0"
NEXT_MAJOR="$((MAJOR + 1)).0.0"

# ── Parse args or prompt interactively ─────────────────────────────
BUMP="${1:-}"
DESCRIPTION=""

# Parse -m flag (can be $2/$3 or $1/$2)
shift_count=0
while [[ $# -gt 0 ]]; do
    case "${1:-}" in
        -m) DESCRIPTION="${2:-}"; shift 2 ;;
        patch|minor|major) [[ -z "$BUMP" ]] && BUMP="$1"; shift ;;
        *) [[ -z "$BUMP" ]] && BUMP="$1"; shift ;;
    esac
done

if [[ -n "$BUMP" ]]; then
    # Non-interactive: resolve version from arg
    case "$BUMP" in
        patch)   NEW_VERSION="$NEXT_PATCH" ;;
        minor)   NEW_VERSION="$NEXT_MINOR" ;;
        major)   NEW_VERSION="$NEXT_MAJOR" ;;
        *.*.*)   NEW_VERSION="$BUMP" ;;
        *) echo "Invalid bump type: $BUMP"; exit 1 ;;
    esac
    DESCRIPTION="${DESCRIPTION:-release v$NEW_VERSION}"
    echo "Current version: $CURRENT"
else
    # Interactive mode
    echo "Current version: $CURRENT"
    echo ""
    echo "  1) patch  → $NEXT_PATCH   (bug fixes, small changes)"
    echo "  2) minor  → $NEXT_MINOR   (new features, backwards compatible)"
    echo "  3) major  → $NEXT_MAJOR   (breaking changes)"
    echo "  4) custom"
    echo ""
    read -rp "Bump type [1]: " CHOICE
    CHOICE=${CHOICE:-1}

    case "$CHOICE" in
        1|patch) NEW_VERSION="$NEXT_PATCH" ;;
        2|minor) NEW_VERSION="$NEXT_MINOR" ;;
        3|major) NEW_VERSION="$NEXT_MAJOR" ;;
        4|custom)
            read -rp "Version: " NEW_VERSION
            if [[ -z "$NEW_VERSION" ]]; then
                echo "No version provided. Aborting."
                exit 1
            fi
            ;;
        *) echo "Invalid choice. Aborting."; exit 1 ;;
    esac

    read -rp "Short description: " DESCRIPTION
    DESCRIPTION="${DESCRIPTION:-release v$NEW_VERSION}"
fi

# ── Bump version in both files ─────────────────────────────────────
echo ""
echo "Bumping $CURRENT → $NEW_VERSION..."
sed -i "s/^version = \"$CURRENT\"/version = \"$NEW_VERSION\"/" pyproject.toml
sed -i "s/__version__ = \"$CURRENT\"/__version__ = \"$NEW_VERSION\"/" jhcontext/__init__.py

# ── Verify versions match ──────────────────────────────────────────
V_TOML=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
V_INIT=$(grep '__version__' jhcontext/__init__.py | sed 's/.*"\(.*\)"/\1/')
if [[ "$V_TOML" != "$NEW_VERSION" || "$V_INIT" != "$NEW_VERSION" ]]; then
    echo "ERROR: Version mismatch after bump (toml=$V_TOML, init=$V_INIT)"
    exit 1
fi
echo "  pyproject.toml: $V_TOML"
echo "  __init__.py:    $V_INIT"

# ── Run tests ──────────────────────────────────────────────────────
echo "Running tests..."
python -m pytest tests/ --ignore=tests/test_example.py -q || {
    echo "Tests failed. Fix before releasing."
    git checkout -- pyproject.toml jhcontext/__init__.py
    exit 1
}

# ── Git commit + tag + push ────────────────────────────────────────
# Pushing the tag triggers GitHub Actions → build → upload to PyPI
echo "Committing and tagging..."
git add -A
git commit -m "v$NEW_VERSION — $DESCRIPTION"
git tag "v$NEW_VERSION"
# Push commit first, then tag separately — pushing together causes
# GitHub Actions to fire only the branch event, skipping the publish job.
git push origin main
git push origin "v$NEW_VERSION"

echo ""
echo "=== v$NEW_VERSION pushed ==="
echo "  GitHub Actions will build and publish to PyPI automatically."
echo "  Watch: https://github.com/jhcontext/jhcontext-sdk/actions"
echo "  PyPI:  https://pypi.org/project/jhcontext/$NEW_VERSION/ (after CI completes)"
