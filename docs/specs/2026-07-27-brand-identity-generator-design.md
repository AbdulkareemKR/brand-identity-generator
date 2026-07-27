# Brand Identity Generator — public repo + site design

Approved by Abdulkareem 2026-07-27.

## Goal
Publish the private `brand-identity` Claude Code skill as a public GitHub repo with a
visually strong landing site so anyone can generate agency-grade brand guideline decks.

## Repo (public, AbdulkareemKR/brand-identity-generator, MIT)
```
README.md            hero visual, what it makes, 4-step process, keys, install, gallery
skill/SKILL.md       the skill, verbatim copy
skill/scripts/       process_logo.py, gen_mockups.py (publishable templates, env keys only)
examples/terra/      demo brand: mini deck + real AI mockups
docs/                website, served by GitHub Pages (Pages from /docs on main)
```
Install story: `git clone` into `~/.claude/skills/`, then ask Claude Code for a brand
identity. Keys documented: `GEMINI_API_KEY` (logo-bearing mockups, Gemini 2.5 flash
image), `OPENAI_API_KEY` (illustrations/patterns, gpt-image-1). Both optional; deck
renders free via headless Chrome.

## Website (static, docs/)
- Hero with animated deck-page showcase, how-it-works steps, example gallery.
- Brief builder: upload logo (stays in browser; canvas samples palette live, shows
  swatches) or from-scratch mode; industry, theme chips, language EN/AR/bilingual;
  outputs a tailored brief plus install command, copy buttons.
- SEO: keyword-rich title/meta, OpenGraph image, JSON-LD (SoftwareApplication +
  FAQPage), sitemap.xml, robots.txt, semantic HTML. No ranking guarantees; this is
  full on-page SEO.

## Demo brand — Terra
Fictional specialty coffee brand, earthy palette (opposite of author's pastel Cutie,
proves range). Mini deck ~10 pages: cover, contents, logo, colors, type, voice,
3 application pages with real Gemini mockups, thank you. Page renders feed the site
gallery and README.

## Non-goals
No hosted generation backend, no key handling on the site, no user accounts.
