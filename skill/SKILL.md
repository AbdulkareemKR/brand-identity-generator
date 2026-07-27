---
name: brand-identity
description: Use when creating a complete brand identity / design system / brand guideline for a company or product, either from scratch or from a logo the user already has — generates a professional landscape 16:9 brand deck (logo, color, type, voice, applications) as self-contained HTML exported to PDF, with real AI-generated mockup images. Triggers: "brand identity", "brand guidelines", "design system", "brand book", "style guide", "brand deck", "logo design".
---

# Brand Identity / Design System Generator

Produce an investor grade brand guideline as a **landscape 16:9 slide deck** in one self contained HTML file, exported to PDF via headless Chrome. Applications are shown as **real AI generated mockup photos**, not CSS drawings. Repeatable for any brand, any language.

## Three entry modes (decide first)
- **Mode A — from scratch.** No assets exist. Invent the name motif, palette, type, and build a logo (see Logo section: show 6 to 8 options, get a pick).
- **Mode B — from a provided logo (most common).** The user hands you a logo and wants the whole system built around it. Do NOT redraw or restyle their logo. Keep its text exactly as given. Extract everything FROM the logo: sample its palette, rebuild clean asset PNGs, then generate the full deck. See "Processing a provided logo".
- **Mode C — from an existing brand (website or old guideline).** Multiple identity sources may CONFLICT (an old guideline PDF vs a redesigned website). Do not assume either is ground truth: the newest shipped surface usually wins, but ASK THE USER which identity is current before building 40 slides on it; picking wrong forces a full rebuild. To harvest assets from a guideline PDF: `pdfimages -png` (merge each RGB image with its following `smask` gray image into RGBA via PIL `putalpha`), render pages at 200 dpi and sample exact palette swatches. To harvest from a website: pull inline SVG symbols, base64 data URIs, CSS custom properties (the real token palette), and Google Fonts links from the HTML.

Confirm which mode, then confirm color + logo direction BEFORE building 30+ slides. Reversing later is expensive.

## Required context (gather first, do not infer from code)
Brand name, product, market and geography, target audience and use case, personality and tone (as extremes), locked assets (name, colors, fonts). Ask 2 to 4 crisp multiple choice questions if missing, then proceed.

## Copy rules (read before writing any slide text)
- **No hyphens or dashes anywhere in body copy.** No hyphen, no en dash, no em dash. Write clean sentences instead. "navy and cream", not "navy-and-cream". "true to the brand", not "on-brand". Break a dash clause into two sentences or use a comma. Dimensions like `85 × 55 mm` and the middot in `ONQ · عنق` are fine. This is a hard client preference; a review pass must catch stray dashes.
- Sentence case for notes and captions. No filler. Say the thing.

## Processing a provided logo (Mode B)
Use `scripts/process_logo.py` (PIL only) as the starting point. Goal: a small set of clean, reusable PNGs plus a sampled palette.
- **Save the source** as a high resolution PNG on a transparent or flat background.
- **Color variants:** keep the given wordmark as is (ink/navy). Make a **white variant** by recoloring every non transparent pixel white (for dark and primary backgrounds).
- **Isolate the symbol/mark:** scan columns for ink (column presence runs), take the run that is the mark only, crop it, pad to a **square**. Verify you grabbed the mark and not a stray letter or diacritic; a too wide crop grabs neighboring glyphs. Re crop if wrong.
- **App badge:** the mark centered on a rounded square in the primary color, no extra plate or background box.
- **Sample the palette** from the logo pixels (most common non neutral colors), then refine to clean hexes for the color section.
- **Reuse these exact PNGs everywhere** (cover, closing, lockups, and as the reference image for every AI mockup). If a real logo exists, never rebuild its letters in HTML or SVG; a font `@import` inside an SVG-as-`<img>` renders a different fallback font and the cover will not match inner pages.

## Deck structure — mirror a real agency deck (8 sections)
Cover → Contents (numbered 01 to 08, two columns) → then per section a **dark divider** (giant number + title, alternate ink and primary background) followed by content slides:
1. **Logo & Sub-logos** — meaning slide, lockups + clear space (X unit grid, min sizes, app badge), variants on color + misuse do and don'ts, sub logos/collections (sub brands keep the master mark + a descriptor + their own accent).
2. **Values & Personality** — 3 to 5 values in big overlapping type, personality sliders on WAVY tracks (inline SVG sine path, `preserveAspectRatio="none"`, dot overlaid at a percentage) with the two extremes labelled at both ends; straight thin lines look unfinished. Title the slide with the industry term (شخصية العلامة / Brand Personality), not an invented phrase.
3. **Voice** — wavy tone sliders + say / do not say.
4. **Colors** — split **primary vs secondary** and size each swatch PROPORTIONALLY to its usage share (flex values = percentages: e.g. cream 45 / navy 30 / orange 15 as tall blocks, secondary accents as a smaller row). Label each block with name, share, HEX/RGB inside the swatch. Equal width columns read as "all colors are equal" and clients reject it.
5. **Typography** — big Aa specimen + weights, pairing (display + body) + a second script if bilingual, type scale.
6. **Photography** — real photo grid + do and don't, full bleed lifestyle hero.
7. **Elements, Patterns & Components** — motif, pattern, scallops, buttons/tags/product card UI kit, spot illustrations.
8. **Applications** — see the expanded rules below.

A rich deck is 35 to 45 slides. Close with a **THANK YOU divider** (primary background, giant thanks, motif).

## Applications — one product per page, multiple angles (best practice)
Give **each product type its own page** (sometimes two). Show **2 or 3 different angles** of that one product, not two unrelated products crammed onto one slide. Cover all aspects of the object.
- **Business cards:** build in **HTML, not AI** — crisp text with a realistic sample identity (name, position, phone, email, site). Front with data + back with the logo, shown as two large rounded cards with drop shadows and a slight opposing rotate.
- **Employee ID cards:** HTML too — front card with an AI generated portrait in a circle (generate a corporate headshot, crop away any corner artifacts), name, role, ID number; back card in the primary color with the logo and site.
- **Notebooks:** closed hardcover, open dotted grid interior, and a stack of the color variants.
- **Stationery:** letterhead A4, presentation folder, envelope and set.
- **Uniform:** ghost mannequin flats (front, back) PLUS at least one worn shot. Frame worn shots "strictly from the SHOULDERS DOWN, head and face completely outside the frame" — "neck to waist" still leaks a chin; crop any residual face sliver off the cutout in post. Put polos, t shirts, and vests on separate pages.
- **A bare swoosh/tick mark on apparel reads as the Nike logo** (the model literally draws Nike's swoosh) — but some clients still insist on the bare mark, no badge box, on clothes. The reliable recipe either way: generate the garment COMPLETELY BLANK, then stamp the exact mark PNG on the chest with PIL `alpha_composite` (slightly reduced alpha ~90% so it sits into the fabric). Asking the model to print the mark gets flame-like mutations half the time.
- **Fixing a wrong printed mark in post:** never auto-detect it with a white-pixel mask — mannequin necks and white shirts match and the patch destroys the image. Instead render the cutout with a red coordinate grid overlay, READ it visually, hardcode the bbox, patch with fabric sampled from BESIDE/BELOW at the same height (never above — that is collar or shirt), then stamp the mark PNG. Re-render and re-check; expect one iteration of coordinate correction.
- **Worn shots:** "framed neck to waist" gives an ugly hard-cropped neck and a post-crop looks worse. Prompt "the model's head is naturally outside the top edge of the frame, like a standard clothing ecommerce photo" — a crop through the lower face at the frame edge is normal catalog style and reads fine.
- **Cups page:** ceramic mug with the mark LARGE (not a small pasted patch), a thin ornament band (arabesque works for Arabic brands), plus a row of takeaway paper cups with a patterned sleeve. Small marks slapped mid-mug read as cheap stickers and clients reject them.
- **Cups:** front, angled motif wrap, and a row of sizes.
- **Stickers:** build the sheet in **HTML, not AI** — die cut pills and circles with witty audience culture phrases (for a reading app: "صفحة أخيرة… أوعدك", "لا تزعجني، أنا أقرأ", coffee and book jokes), the mascot PNG, the badge, and small inline SVG line icons. AI sticker sheets come out as empty dots; HTML gives crisp text and real personality. Lay the sheet out with FLEX ROWS, never absolute positioning — RTL pill widths are unpredictable and absolutely positioned stickers overlap. Screenshot at `--force-device-scale-factor=2`. Show the sheet plus an applied on laptop photo.
- **Spot icons page:** don't show one long AI strip image; slice it into individual icons (find dark column runs with numpy, crop each with padding) and present each icon in its own white card with an Arabic label. A strip with an icon touching the slide edge reads as a bug.
- **Mascot merch page:** a photo collage grid (one large cell + 3 or 4 small) of the mascot as physical objects in real scenes — plush on an office desk (local dress details sell it, e.g. a tiny shmagh), rubber keychain with keys, plush sitting on a bookshelf, held in hands. Generate scenes with the mascot PNG as reference; keep these as photos, not cutouts.
- **Mascot 2D vs plush:** if the brand has a flat 2D mascot, use the FLAT version on cover, sub brand, and closing slides; the plush 3D render belongs only on the merchandise page. If the only source is a tiny favicon (120px), regenerate a crisp flat version with AI ("flat 2D vector, entire body the same solid brand color including the face, NO white face panel, no texture, no 3D shading") and rembg it — expect one retry because the model loves inventing a white face.
- Plus: packaging/unboxing, storefront/signage, billboard, bus, web, and social banners, app UI + app icon.
- **Billboards and ad screens:** the screen must show a COMPLETE ad (logo, headline, sub line, CTA pill), never the logo alone, on its OWN page with the panel FULLY visible in a bright appealing street scene (daytime beats dusk). Build the ad creative in HTML at the panel's aspect ratio and screenshot it. Compositing: upscale the scene ~1.6× first, paste the ad at that resolution, then UnsharpMask — pasting a small downscaled ad reads blurry. Measure the panel bounds by eye from a preview; naive dark-pixel masks catch cars and shadows and misplace the paste.
- **Certificates:** build these in **HTML, not AI** (crisp vector text). Appreciation + completion, framed with a double border, a circular seal holding the mark, a PRINTED sample recipient name over the name line, and signature/date lines.

**Cutout presentation (clients prefer this over photo boxes):** generate each product as a catalog packshot ("plain flat light gray background, product fully visible with generous margin, nothing cropped"), then strip the background with `rembg` (pip install rembg onnxruntime in a venv), crop to bbox, and place the transparent PNG directly on the slide with `filter: drop-shadow(...)` and a pill caption. Reserve `object-fit:cover` photo cards for context scenes (billboard street, laptop desk). Worn apparel shots get the same rembg treatment — the person floats too. Composite the real wordmark PNG onto flat cutout areas (shirt chest, notebook cover, tote body) with PIL `alpha_composite` instead of trusting AI to print it.

Layout for a multi angle page: an absolutely positioned `.approw` (inset), `display:flex`, three `.card`s, each holding an image box `.im` (`object-fit:cover`) and a caption `.cap`. Request landscape framing from the image generator so cover cropping stays clean.

"Add N more example slides" means more application pages, each following the one product per page rule.

## Logo (make it a real mark, not just a font)
- Simple, memorable, hand drawable, ONE conceptual hook that repeats. Provide wordmark + symbol + app badge. No emoji or clip art.
- **Mode A, show options before committing:** render 6 to 8 variants on a grid (different fonts, motif placements, tilt), screenshot, let the user pick, iterate.
- **Build the master wordmark ONE way and reuse that exact markup or PNG everywhere.** Identical source means identical font on cover, closing, meaning, and lockups.
- **Colored accent letter trick:** one letter in the accent color makes a plain wordmark feel branded.
- **Background aware color versions** and USE the right one per slide background: light or tint background gets ink letters + accent, primary color background gets all white, dark/ink background gets cream letters + accent.
- Put the branded master logo on the first page (light cover uses the colored version, bold primary color cover uses the white version).

## Non-Latin / bilingual logo & RTL deck
Separate file, same concept. AI mangles non Latin letterforms, so hand build the master as SVG or reuse the provided PNG. Motif trick: exploit a letter's natural stroke. `dir="rtl"`, script font primary + a Latin font for numbers and Latin runs, `font-family:'Cairo','Poppins'`. Mirror divider positioning (number on the right, title on the left). **RTL flexbox reverses inline wordmark pieces**, so wrap any Latin wordmark in `direction:ltr; unicode-bidi:isolate`. Watch for left/right absolute position collisions when flipping.

Generate the RTL variant by transforming the finished Latin deck: swap `left`↔`right` on box and position CSS with a scoped regex, run the visible strings through a translation dict, and set the RTL font stack. Keep the logo text bilingual or exactly as given. Localize captions, notes, and eyebrows. Re check for any missed strings and mirrored positions.

## Real mockup images (the key quality lever)
Generate application mockups with AI using the user's own keys (env `OPENAI_API_KEY`, `GEMINI_API_KEY`). See `scripts/gen_mockups.py`; it has a CONFIG block to edit per brand.
- **Gemini 2.5-flash-image** (`gemini-2.5-flash-image:generateContent`) — pass the real logo PNG as `inline_data` + "use the provided logo EXACTLY, do NOT redraw the letters or mark" + the exact palette hexes + "no people, soft studio light, cream background". Best for on brand mockups. Retry 3×; the image is base64 in `candidates[0].content.parts[*].inlineData.data`.
- **Absolutely no text guard:** AI loves to invent garbled foreign letters (fake Arabic, gibberish). Add "Absolutely NO text, letters or numbers anywhere except the provided logo." Verify every mockup and regenerate any with invented text.
- **Arabic wordmarks with shadda or hamza get mangled** even when passed as a reference (the ء drops). Reliable recipe: generate the product with only the symbol/badge, or fully blank, then composite the real wordmark PNG in post on flat surfaces. Also: asking for a "completely blank" tote or billboard often gets an invented fake logo instead — re-prompt as "unbranded blank product before printing, catalog shot"; a torn or zigzag card stack edge is an artifact worth one regen ("crisp straight clean edges"); "solid filled logo, do NOT redraw as an outline, do NOT enlarge into a wrap pattern" stops the two most common logo mutations on mugs and apparel.
- **App icon:** ask for "clean, isolated, no background plate or square", otherwise it adds a gray tile behind the icon.
- **Ghost mannequin** for apparel: "on an invisible ghost mannequin, no person, empty".
- **OpenAI gpt-image-1** (`/v1/images/generations`, `b64_json`) — flat vector illustrations, seamless patterns, illustrated scenes.
- A logo neutral image (lifestyle photo, illustration, pattern) can be reused across language variants; only regenerate logo bearing mockups.
- Build a contact sheet and VISUALLY verify before wiring in. Zoom logo bearing shots to confirm the letters survived.

## Image optimization (do before shipping)
Downscale every mockup to ≤1600px wide and save as **JPG quality 85 progressive**; repoint `<img>` refs from `.png` to `.jpg`. Keep logos and marks as **PNG** for transparency. This typically cuts a deck from ~30 MB to ~2 MB and makes the PDF render and open far faster.

## Build & export
Self contained HTML, each slide a fixed `1280×720` div, Google Fonts, real images via relative `<img>`.
Print CSS: `@page{size:1280px 720px;margin:0}`, `print-color-adjust:exact`, `.slide{page-break-after:always}`, no animations.
Export: `"/Applications/Google Chrome.app/Contents/MacOS/Google Chrome" --headless=new --no-pdf-header-footer --virtual-time-budget=16000 --print-to-pdf="<Name>.pdf" deck.html` (raise virtual time budget when there are many images). If headless does not self exit, kill it after the PDF is written.

## Rendering artifacts to avoid
- **Slider and personality dots:** flat fill only, no `box-shadow`; a shadow prints as a square halo around the circle.
- **`box-shadow` prints as a solid colored RECTANGLE in headless Chrome PDF export** — on cards, seals, any element. Never use box-shadow anywhere in a deck; use `filter: drop-shadow(...)` instead (it rasterizes correctly). When stripping box-shadows with a regex, remember the last property in a style attribute has NO trailing semicolon — `box-shadow:[^;"]+;` misses it and the colored box survives.
- **Page numbers:** `.pg` markers may carry an inline `style` attribute; renumber ALL of them sequentially with a regex that ignores attributes, after any slide insert or delete.
- **Marks:** never wire in the old inline placeholder mark once a real logo PNG exists; replace every instance.

## Mandatory review before submitting
`pdftoppm -png -r 60 file.pdf out`, build 6 per page montages with PIL, and Read EVERY page. Fix: garbled AI text, gray icon plates, clipped or cropped art, text overlapping the logo, wrong or duplicate page numbers, **any hyphen or dash in copy**, font mismatches, placeholders. Zoom each logo bearing mockup to confirm the letters are intact and correct.

## Anti-slop
"Could someone tell an AI made this?" If yes, push harder. Vary the aesthetic per brand. Rounded or pastel only when intentional and precise (spacing, hierarchy, restraint). Tint neutrals toward the hero hue; never pure black or white text.
