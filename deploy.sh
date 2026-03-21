#!/usr/bin/env bash
set -euo pipefail

cd "$(dirname "${BASH_SOURCE[0]}")"

# ── Get current version ────────────────────────────────────────────
CURRENT=$(grep '^version' pyproject.toml | head -1 | sed 's/.*"\(.*\)"/\1/')
MAJOR=$(echo "$CURRENT" | cut -d. -f1)
MINOR=$(echo "$CURRENT" | cut -d. -f2)
PATCH=$(echo "$CURRENT" | cut -d. -f3)

# ── Auto-increment options ─────────────────────────────────────────
NEXT_PATCH="$MAJOR.$MINOR.$((PATCH + 1))"
NEXT_MINOR="$MAJOR.$((MINOR + 1)).0"
NEXT_MAJOR="$((MAJOR + 1)).0.0"

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

# ── Ask for description ────────────────────────────────────────────
read -rp "Short description: " DESCRIPTION
if [[ -z "$DESCRIPTION" ]]; then
    DESCRIPTION="release v$NEW_VERSION"
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
git push origin main --tags

echo ""
echo "=== v$NEW_VERSION pushed ==="
echo "  GitHub Actions will build and publish to PyPI automatically."
echo "  Watch: https://github.com/jhcontext/jhcontext-sdk/actions"
echo "  PyPI:  https://pypi.org/project/jhcontext/$NEW_VERSION/ (after CI completes)"
