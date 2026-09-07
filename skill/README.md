# brand-identity — portable Claude skill

Generates investor grade brand guidelines (landscape 16:9 PDF deck) with real
AI generated mockups. Language agnostic (Latin + RTL/Arabic).

Two ways in: **from scratch** (invent name, palette, logo), or **from a logo the
user already has** (extract the palette, rebuild clean assets, build the whole
system around it). Body copy carries no hyphens or dashes by rule.

## Install — one line (easiest)
    curl -fsSL https://brand.sadaorg.com/install.sh | bash
Drops the skill into `~/.claude/skills/brand-identity/` and you are done. Or grab
the zip from https://brand.sadaorg.com and unzip it into that same folder.

## Install manually
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
- `scripts/gen_mockups.py` — GPT only (`gpt-image-1`) helpers to composite the real
  logo onto product mockups, one product per entry with several angles, then optimize
  to JPG (needs env `OPENAI_API_KEY`, or `NETZERO_OPENAI_API_KEY` for Netzero billing).
  Logo-bearing products use `/v1/images/edits` with `input_fidelity: high`; neutral art
  uses `/v1/images/generations`. Edit its CONFIG block. No Gemini.

## Requirements on the machine
- Headless Chrome (for HTML→PDF)
- `pdftoppm` (poppler) + Python PIL/pypdf for the review step
- `OPENAI_API_KEY` in env for AI mockups (optional; deck works without it). No Gemini key needed.
