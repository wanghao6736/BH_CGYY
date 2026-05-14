#!/usr/bin/env bash
# Install CGYY skill to Claude Code / Codex skill directories.
# Run from project root: bash scripts/install-cgyy-skill.sh
set -euo pipefail

SKILL_SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")/../skills/cgyy" && pwd)"
SKILL_NAME="cgyy"

# ── Claude Code ──
CLAUDE_SKILLS="$HOME/.claude/skills"
if [ -d "$CLAUDE_SKILLS" ] || [ -d "$HOME/.claude" ]; then
    mkdir -p "$CLAUDE_SKILLS/$SKILL_NAME"
    cp -r "$SKILL_SRC/"* "$CLAUDE_SKILLS/$SKILL_NAME/"
    echo "✓ Installed to Claude Code: $CLAUDE_SKILLS/$SKILL_NAME"
fi

# ── Codex ──
CODEX_SKILLS="$HOME/.agents/skills"
if [ -d "$CODEX_SKILLS" ] || [ -d "$HOME/.agents" ]; then
    mkdir -p "$CODEX_SKILLS/$SKILL_NAME"
    cp -r "$SKILL_SRC/"* "$CODEX_SKILLS/$SKILL_NAME/"
    echo "✓ Installed to Codex: $CODEX_SKILLS/$SKILL_NAME"
fi

echo ""
echo "Done. Restart your AI coding tool or run /reload-plugins to pick up the skill."
