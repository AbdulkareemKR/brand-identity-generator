#!/usr/bin/env bash
# Brand Identity Generator skill installer.
# Usage: curl -fsSL https://brand.sadaorg.com/install.sh | bash
set -euo pipefail

DEST="${CLAUDE_SKILLS_DIR:-$HOME/.claude/skills}/brand-identity"
URL="https://brand.sadaorg.com/brand-identity-skill.zip"
TMP="$(mktemp -d)"
trap 'rm -rf "$TMP"' EXIT

command -v unzip >/dev/null || { echo "unzip is required, install it first."; exit 1; }

echo "Downloading the brand-identity skill..."
curl -fsSL "$URL" -o "$TMP/skill.zip"
unzip -q -o "$TMP/skill.zip" -d "$TMP"
[ -d "$TMP/brand-identity" ] || { echo "Unexpected zip layout, aborting (nothing changed)."; exit 1; }

mkdir -p "$(dirname "$DEST")"
if [ -d "$DEST" ]; then
  echo "Updating existing install at $DEST"
  rm -rf "$DEST"
fi
mv "$TMP/brand-identity" "$DEST"

echo ""
echo "Installed to $DEST"
echo "Open Claude Code anywhere and say: build me a brand identity"
