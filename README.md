# brand-identity — Claude Code skill

Designs a complete, agency grade brand identity: logo system, colors,
typography, voice, and real AI product mockups, delivered as a polished
16:9 brand guideline deck (HTML + PDF). Latin and RTL Arabic.

Try the hosted version first: **[brand.sadaorg.com](https://brand.sadaorg.com)**
(that site's source lives in [brand-studio](https://github.com/AbdulkareemKR/brand-studio)).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/AbdulkareemKR/brand-identity-generator/main/install.sh | bash
```

Or copy this repo's `SKILL.md` + `scripts/` into `~/.claude/skills/brand-identity/`.

Then in [Claude Code](https://claude.com/claude-code):

```
create a brand identity for my coffee shop "terra" — earthy, artisanal, warm
```

Triggers: brand identity, brand guidelines, design system, brand book, style guide, brand deck, logo design.

## What is here

```
SKILL.md                  the full method
scripts/process_logo.py   provided logo -> clean PNG set + clustered palette + app badge
scripts/gen_mockups.py    gpt-image-1 mockup engine (edits + generations), CONFIG per brand
```

## Requirements

- `OPENAI_API_KEY` in env for AI mockups (optional; the deck builds without it)
- Headless Chrome for HTML to PDF, poppler + Pillow for the review pass

MIT.
