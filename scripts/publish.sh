#!/usr/bin/env bash
# publish.sh — Build and publish arkforge-trustlayer-client to PyPI
#
# Usage: ./scripts/publish.sh [--minor|--major] [--skip-tests]
#
# Flags:
#   --minor       Bump minor version (1.9.x → 1.10.0)
#   --major       Bump major version (1.x.x → 2.0.0)
#   (default)     Bump patch (1.9.0 → 1.9.1)
#   --skip-tests  Skip pytest (use for hotfixes)

set -euo pipefail

REPO_DIR="$(cd "$(dirname "$0")/.." && pwd)"
LOG_FILE="$REPO_DIR/logs/publish.log"
PYPI_PACKAGE="arkforge-trustlayer-client"

# --- Args ---
VERSION_BUMP="patch"
SKIP_TESTS=false
for arg in "$@"; do
    case "$arg" in
        --minor)       VERSION_BUMP="minor" ;;
        --major)       VERSION_BUMP="major" ;;
        --skip-tests)  SKIP_TESTS=true ;;
    esac
done

# --- Logging ---
mkdir -p "$(dirname "$LOG_FILE")"
log() { echo "[$(date -u +%Y-%m-%dT%H:%M:%SZ)] $*" | tee -a "$LOG_FILE"; }
fail() { log "ERROR: $*"; exit 1; }

# --- Version bump helper ---
bump_version() {
    local current="$1" bump="$2"
    local major minor patch
    major=$(echo "$current" | cut -d. -f1)
    minor=$(echo "$current" | cut -d. -f2)
    patch=$(echo "$current" | cut -d. -f3)
    case "$bump" in
        major) echo "$((major + 1)).0.0" ;;
        minor) echo "${major}.$((minor + 1)).0" ;;
        patch) echo "${major}.${minor}.$((patch + 1))" ;;
    esac
}

cd "$REPO_DIR"

# Check branch
CURRENT_BRANCH=$(git rev-parse --abbrev-ref HEAD)
if [ "$CURRENT_BRANCH" != "main" ]; then
    fail "Not on main branch (current: $CURRENT_BRANCH). Switch to main before publishing."
fi

git pull origin main >> "$LOG_FILE" 2>&1

log "=== Publish $PYPI_PACKAGE — $(date -u) ==="
log "Version bump: $VERSION_BUMP | Skip tests: $SKIP_TESTS"

# ============================================================
# PHASE 1 — TESTS
# ============================================================
if [ "$SKIP_TESTS" = true ]; then
    log "--- Phase 1: Tests SKIPPED (--skip-tests) ---"
else
    log "--- Phase 1: Tests ---"
    if ! python3 -m pytest tests/ -q --tb=short >> "$LOG_FILE" 2>&1; then
        fail "Tests FAILED — aborting publish"
    fi
    log "Phase 1: Tests OK"
fi

# ============================================================
# PHASE 2 — VERSION BUMP
# ============================================================
log "--- Phase 2: Version bump ---"

# Read current version from pyproject.toml (source of truth for the package)
CURRENT=$(grep '^version' pyproject.toml | grep -oP '[\d.]+')
NEW=$(bump_version "$CURRENT" "$VERSION_BUMP")
log "Version: $CURRENT → $NEW"

# 1. pyproject.toml
sed -i "s/^version = .*/version = \"$NEW\"/" pyproject.toml

# 2. src/arkforge/version.py (SDK __version__)
sed -i "s/__version__ = .*/__version__ = \"$NEW\"/" src/arkforge/version.py

# 3. agent.py AGENT_VERSION (CLI + HTTP header)
sed -i "s/^AGENT_VERSION = .*/AGENT_VERSION = \"$NEW\"/" agent.py

log "Phase 2: pyproject.toml + src/arkforge/version.py + agent.py bumped to $NEW"

# ============================================================
# PHASE 3 — BUILD + PUBLISH
# ============================================================
log "--- Phase 3: Build ---"
rm -rf dist/
if ! python3 -m build -q >> "$LOG_FILE" 2>&1; then
    fail "Build FAILED"
fi
log "Phase 3: Build OK"

log "--- Phase 4: Publish to PyPI ---"
if ! twine upload dist/* -q >> "$LOG_FILE" 2>&1; then
    fail "PyPI upload FAILED"
fi
log "Phase 4: $PYPI_PACKAGE $NEW published to PyPI"

# ============================================================
# PHASE 5 — GIT TAG + PUSH
# ============================================================
log "--- Phase 5: Git commit + tag + push ---"

LAST_TAG=$(git tag --sort=-v:refname | head -1)
if [ -z "$LAST_TAG" ]; then LAST_TAG="v0.0.0"; fi
NEW_TAG="v$NEW"

CHANGELOG=$(git log "${LAST_TAG}..HEAD" --oneline --no-merges 2>/dev/null | head -20 | sed 's/^/• /' || echo "• No changelog available")

git add pyproject.toml src/arkforge/version.py agent.py
git commit -m "chore(release): $PYPI_PACKAGE $NEW" >> "$LOG_FILE" 2>&1
git tag "$NEW_TAG"
git push origin main >> "$LOG_FILE" 2>&1
git push origin "$NEW_TAG" >> "$LOG_FILE" 2>&1
log "Tag $NEW_TAG pushed"

# ============================================================
# DONE
# ============================================================
log "=== Publish $NEW COMPLETE ==="
echo ""
echo "  $PYPI_PACKAGE $NEW published"
echo "  PyPI: https://pypi.org/project/$PYPI_PACKAGE/$NEW/"
echo "  Tag:  $NEW_TAG"
echo "  Changelog since $LAST_TAG:"
echo "$CHANGELOG"
