#!/usr/bin/env bash
# Brand Identity Generator skill installer.
# Usage: curl -fsSL https://raw.githubusercontent.com/AbdulkareemKR/brand-identity-generator/main/install.sh | bash
set -euo pipefail

DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/brand-identity"
TARBALL="https://codeload.github.com/AbdulkareemKR/brand-identity-generator/tar.gz/refs/heads/main"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading the brand-identity skill..."
curl -fsSL "$TARBALL" | tar -xz -C "$TMP"
SRC="$TMP/brand-identity-generator-main"
[ -f "$SRC/SKILL.md" ] || { echo "Unexpected repo layout, aborting (nothing changed)."; exit 1; }

mkdir -p "$DEST/scripts"
cp "$SRC/SKILL.md" "$SRC/README.md" "$DEST/" 2>/dev/null || cp "$SRC/SKILL.md" "$DEST/"
cp "$SRC"/scripts/*.py "$DEST/scripts/"

echo ""
echo "Installed to $DEST"
echo "Open Claude Code anywhere and say: build me a brand identity"
