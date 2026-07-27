# brand-identity — portable Claude skill

Generates investor grade brand guidelines (landscape 16:9 PDF deck) with real
AI generated mockups. Language agnostic (Latin + RTL/Arabic).

Two ways in: **from scratch** (invent name, palette, logo), or **from a logo the
user already has** (extract the palette, rebuild clean assets, build the whole
system around it). Body copy carries no hyphens or dashes by rule.

## Install in any Claude Code session / machine
Copy this whole `brand-identity/` folder into the target's skills dir:

    ~/.claude/skills/brand-identity/          # user-global: every session on that machine

or into a project for repo-scoped use:

    <repo>/.claude/skills/brand-identity/

That's it — Claude auto-discovers it. Trigger with any of:
"brand identity", "brand guidelines", "design system", "brand book",
"style guide", "brand deck", "logo design".

## Contents
- `SKILL.md`         — the full method (two modes, copy rules, structure, logo rules,
  per product multi angle applications, RTL, image optimization, review gate)
- `scripts/process_logo.py` — Mode B: turn a provided logo PNG into clean reusable
  assets (white variant, isolated square mark, sampled palette). PIL only.
- `scripts/gen_mockups.py` — Gemini + OpenAI helpers to composite the real logo
  onto product mockups, one product per entry with several angles, then optimize to
  JPG (needs env `GEMINI_API_KEY` and/or `OPENAI_API_KEY`). Edit its CONFIG block.

## Requirements on the machine
- Headless Chrome (for HTML→PDF)
- `pdftoppm` (poppler) + Python PIL/pypdf for the review step
- API keys in env for AI mockups (optional; deck works without them)
