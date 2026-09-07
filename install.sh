#!/usr/bin/env bash
# Brand Identity Generator skill installer (repo version — no server needed).
# Usage: curl -fsSL https://raw.githubusercontent.com/AbdulkareemKR/brand-identity-generator/main/install.sh | bash
set -euo pipefail

DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/brand-identity"
TARBALL="https://codeload.github.com/AbdulkareemKR/brand-identity-generator/tar.gz/refs/heads/main"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

echo "Downloading the brand-identity skill..."
curl -fsSL "$TARBALL" | tar -xz -C "$TMP"
SRC="$TMP/brand-identity-generator-main/skill"
[ -f "$SRC/SKILL.md" ] || { echo "Unexpected repo layout, aborting (nothing changed)."; exit 1; }

mkdir -p "$(dirname "$DEST")"
if [ -d "$DEST" ]; then
  echo "Updating existing install at $DEST"
  rm -rf "$DEST"
fi
cp -R "$SRC" "$DEST"

echo ""
echo "Installed to $DEST"
echo "Open Claude Code anywhere and say: build me a brand identity"
