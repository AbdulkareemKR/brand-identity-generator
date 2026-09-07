"""
Server-side brand guideline deck builder.

Takes a finished generation job (assets/ + mockup PNGs + palette + brand name)
and renders a 16:9 guideline deck as two PDFs via headless Chrome:

    preview.pdf   free tier — cover, contents, logo, colors, one application,
                  diagonal PREVIEW watermark + an unlock page
    full.pdf      paid tier — the whole document, no watermark

Structure mirrors the skill's standard (cover, contents, dark section dividers,
logo suite, proportional color blocks, type pairing, one product per
application page, thank you). Print rules from the skill: fixed 1280x720
slides, no box-shadow (rasterizes as a solid rectangle), print-color-adjust.

Usage: build_deck(job_dir, name, palette) -> {"preview": path, "full": path}
"""
import os, re, base64, subprocess

CHROME = os.environ.get("CHROME_BIN", "google-chrome")

PRODUCT_CAPTIONS = {
    "business_cards": ("Business cards", "Print collateral leads with the darkest brand color and a flat printed logo."),
    "mug": ("Mug", "The logo sits centered on the visible face, never crowding the handle."),
    "tshirt": ("Apparel", "The mark embroidered small on the chest. Garments stay in brand neutrals."),
    "tote": ("Tote", "Natural cotton carries the logo in its primary color."),
    "app_icon": ("App icon", "The badge stands alone: solid primary square, symbol centered, no text."),
    "notebook": ("Stationery", "Foil stamped mark on the darkest brand color. Small, confident, premium."),
    "signage": ("Signage", "Dimensional letters in daylight. Clear space scales with the letter height."),
    "billboard": ("Out of home", "Panels read as complete ads: logo, accent CTA shape, generous margins."),
}


def _b64(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _luma(hexc):
    h = hexc.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return 0.2126 * r + 0.7152 * g + 0.0722 * b


def _tint(hexc, f=0.92):
    """Mix a color toward white -> pale page background."""
    h = hexc.lstrip("#")
    r, g, b = (int(h[i:i + 2], 16) for i in (0, 2, 4))
    m = lambda v: round(v + (255 - v) * f)
    return "#%02X%02X%02X" % (m(r), m(g), m(b))


def _rgb(hexc):
    h = hexc.lstrip("#")
    return ", ".join(str(int(h[i:i + 2], 16)) for i in (0, 2, 4))


def build_deck(job_dir, name, palette, out_dir=None, preview_only=False):
    out_dir = out_dir or job_dir
    name = (name or "Your brand").strip()[:40]
    pal = [p for p in (palette or []) if re.match(r"^#[0-9a-fA-F]{6}$", p)][:6] or ["#C4633C", "#2E201A", "#F6EEE3"]
    safe_name = (name.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;"))
    # roles: accent = most saturated-ish first entry, dark = lowest luma, light tint from accent
    dark = min(pal, key=_luma)
    accent = pal[0] if pal[0] != dark or len(pal) == 1 else pal[1 % len(pal)]
    paper = _tint(accent, 0.94)
    mint = _tint(accent, 0.85)
    eyebrow = accent if _luma(accent) < 170 else dark

    A = os.path.join(job_dir, "assets")
    def asset(fn):
        p = os.path.join(A, fn)
        return _b64(p) if os.path.exists(p) else None
    logo = asset("logo-navy.png") or asset("mark-navy.png")
    logo_w = asset("logo-white.png") or asset("mark-white.png")
    mark = asset("mark-navy.png") or logo
    mark_w = asset("mark-white.png") or logo_w
    badge = asset("app-badge.png")
    # concept-based jobs store the picked concept as the only asset
    if not logo:
        for d in (job_dir, A):
            if logo or not os.path.isdir(d):
                continue
            for fn in sorted(os.listdir(d)):
                if fn.startswith("concept_") and fn.endswith(".png"):
                    logo = logo_w = mark = mark_w = _b64(os.path.join(d, fn))
                    break
    if not logo:
        raise ValueError("no logo asset in job dir")

    mocks = []
    for key, (title, cap) in PRODUCT_CAPTIONS.items():
        p = os.path.join(job_dir, key + ".png")
        if not os.path.exists(p):
            continue
        # the generated app icon scene drifts (pouches, tiles); the badge asset IS
        # the icon, so show it directly and stay correct every time
        img = badge if (key == "app_icon" and badge) else _b64(p)
        mocks.append((key, title, cap, img))

    css = f"""
    @import url('https://fonts.googleapis.com/css2?family=Sora:wght@400;600;700;800&family=Karla:wght@300;400;600;700&display=swap');
    *{{margin:0;padding:0;box-sizing:border-box}}
    body{{font-family:'Karla',sans-serif;color:{dark};background:#777}}
    .slide{{width:1280px;height:720px;position:relative;overflow:hidden;background:{paper};page-break-after:always;margin:0 auto}}
    h1,h2,h3,.sora{{font-family:'Sora',sans-serif}}
    .pg{{position:absolute;right:40px;bottom:26px;font-size:12px;letter-spacing:.14em;color:{dark};opacity:.5}}
    .eyebrow{{font-size:13px;font-weight:700;letter-spacing:.22em;text-transform:uppercase;color:{eyebrow}}}
    .divider{{background:{dark};color:{paper}}}
    .divider .big{{position:absolute;left:70px;bottom:40px;font-size:200px;font-weight:800;opacity:.14;font-family:'Sora';line-height:1}}
    .divider h2{{position:absolute;left:74px;top:300px;font-size:56px;color:{paper}}}
    .divider .eyebrow{{position:absolute;left:76px;top:270px}}
    .wm{{position:absolute;inset:0;display:grid;place-items:center;pointer-events:none;z-index:9}}
    .wm span{{font-family:'Sora';font-weight:800;font-size:110px;color:{dark};opacity:.07;transform:rotate(-28deg);letter-spacing:.1em}}
    @page{{size:1280px 720px;margin:0}}
    @media print{{body{{background:none}}.slide{{page-break-after:always}}*{{-webkit-print-color-adjust:exact;print-color-adjust:exact}}}}
    """

    wm = '<div class="wm"><span>PREVIEW</span></div>'

    def cover(w=False):
        return f"""<div class="slide" style="background:{dark};display:grid;place-items:center">
        <div style="text-align:center">
          <img src="{logo_w}" style="max-width:520px;max-height:190px;object-fit:contain">
          <div style="margin-top:34px;color:{paper};font-size:26px;font-weight:700;letter-spacing:.06em" class="sora">{safe_name}</div>
          <div style="margin-top:14px;color:{paper};opacity:.85;font-size:15px;letter-spacing:.3em;text-transform:uppercase" class="sora">Brand guidelines</div>
          <div style="margin-top:10px;color:{accent};font-size:13px;letter-spacing:.18em">2026 EDITION</div>
        </div>{wm if w else ''}</div>"""

    def contents(w=False):
        items = ["01 Logo", "02 Color", "03 Typography", "04 Applications", "05 Thank you"]
        lis = "".join(f'<div style="display:flex;gap:26px;align-items:baseline;padding:17px 0;border-bottom:1px solid {mint}"><span class="sora" style="color:{accent};font-weight:800;font-size:22px">{i.split()[0]}</span><span style="font-size:24px;font-weight:600" class="sora">{i.split(maxsplit=1)[1]}</span></div>' for i in items)
        return f"""<div class="slide" style="padding:80px 110px">
        <div class="eyebrow">Overview</div>
        <h1 style="font-size:52px;margin:14px 0 40px">Contents</h1>
        <div style="columns:2;column-gap:80px">{lis}</div>
        <span class="pg">02</span>{wm if w else ''}</div>"""

    def div_slide(num, title, pg, w=False):
        return f"""<div class="slide divider"><span class="eyebrow">Section</span><h2>{title}</h2><div class="big">{num}</div><span class="pg" style="color:{paper}">{pg}</span>{wm if w else ''}</div>"""

    def logo_suite(pg, w=False):
        cells = ""
        tiles = [(logo, "#FDFCFA", "Primary"), (logo_w, dark, "On dark")]
        if mark and mark != logo:  # skip a duplicate tile when the logo IS the mark
            tiles.append((mark, "#FDFCFA", "Mark"))
        tiles.append((badge or mark, mint, "App badge"))
        for src, bg, cap in tiles:
            if not src: continue
            cells += f'<div style="background:{bg};border:1px solid {mint};border-radius:16px;display:grid;place-items:center;padding:26px"><img src="{src}" style="max-width:78%;max-height:120px;object-fit:contain"></div><div style="font-size:12px;letter-spacing:.14em;text-transform:uppercase;color:{accent};font-weight:700;margin:8px 0 0 4px">{cap}</div>'
        return f"""<div class="slide" style="padding:70px 110px">
        <div class="eyebrow">Logo</div>
        <h1 style="font-size:44px;margin:12px 0 8px">Logo variants</h1>
        <p style="font-size:15px;color:{dark};opacity:.75;max-width:60ch;font-weight:300">Use the supplied files exactly as given. Never redraw, stretch, recolor, or crowd the mark. Clear space equals the height of its tallest letter on every side.</p>
        <div style="display:grid;grid-template-columns:repeat(4,1fr);grid-auto-rows:auto;gap:6px 18px;margin-top:34px">{cells}</div>
        <span class="pg">{pg}</span>{wm if w else ''}</div>"""

    def colors(pg, w=False):
        shares = [46, 28, 14, 7, 5][:len(pal)]
        while len(shares) < len(pal): shares.append(3)
        total = sum(shares)
        blocks = ""
        for c, s in zip(pal, shares):
            tcol = "#FFFFFF" if _luma(c) < 150 else dark
            blocks += f"""<div style="flex:{s};background:{c};border-radius:14px;padding:22px 18px;display:flex;flex-direction:column;justify-content:flex-end;min-width:90px">
            <div class="sora" style="color:{tcol};font-weight:700;font-size:17px">{c}</div>
            <div style="color:{tcol};opacity:.8;font-size:11.5px">RGB {_rgb(c)} · {round(100*s/total)}%</div></div>"""
        return f"""<div class="slide" style="padding:70px 110px">
        <div class="eyebrow">Color</div>
        <h1 style="font-size:44px;margin:12px 0 8px">Color palette</h1>
        <p style="font-size:15px;opacity:.75;max-width:58ch;font-weight:300">Each block's width is its share of any layout. The two largest blocks carry backgrounds and type; keep the smallest strictly for accents.</p>
        <div style="display:flex;gap:14px;height:330px;margin-top:36px">{blocks}</div>
        <span class="pg">{pg}</span>{wm if w else ''}</div>"""

    def typography(pg, w=False):
        return f"""<div class="slide" style="padding:70px 110px">
        <div class="eyebrow">Typography</div>
        <h1 style="font-size:44px;margin:12px 0 34px">Type pairing</h1>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:60px">
          <div><div class="sora" style="font-size:120px;font-weight:800;line-height:1">Aa</div>
            <div class="sora" style="font-size:22px;font-weight:700;margin-top:10px">Sora · display</div>
            <p style="font-size:14px;opacity:.7;font-weight:300">Headlines, numbers, navigation. Weights 600 to 800. Tight leading, generous size jumps.</p></div>
          <div><div style="font-family:'Karla';font-size:120px;font-weight:300;line-height:1">Aa</div>
            <div class="sora" style="font-size:22px;font-weight:700;margin-top:10px">Karla · body</div>
            <p style="font-size:14px;opacity:.7;font-weight:300">Paragraphs, captions, interface copy. Weights 300 to 700. Never below 13px in print.</p></div>
        </div>
        <div style="margin-top:36px;border-top:1px solid {mint};padding-top:18px;font-size:15px;opacity:.7;font-weight:300">Swap for your licensed brand faces at the same roles and weights. The system holds as long as display stays bold and body stays quiet.</div>
        <span class="pg">{pg}</span>{wm if w else ''}</div>"""

    def app_page(title, cap, img, pg, w=False):
        return f"""<div class="slide" style="display:grid;grid-template-columns:1fr 1.35fr">
        <div style="padding:80px 20px 80px 90px;display:flex;flex-direction:column;justify-content:center">
          <div class="eyebrow">Applications</div>
          <h1 style="font-size:40px;margin:12px 0 12px">{title}</h1>
          <p style="font-size:15px;opacity:.75;font-weight:300;max-width:34ch">{cap}</p>
        </div>
        <div style="padding:44px 60px 44px 0;display:grid;place-items:center">
          <img src="{img}" style="max-width:100%;max-height:100%;object-fit:contain;border-radius:18px">
        </div>
        <span class="pg">{pg}</span>{wm if w else ''}</div>"""

    def unlock():
        return f"""<div class="slide divider" style="display:grid;place-items:center">
        <div style="text-align:center;max-width:640px">
          <div class="eyebrow" style="letter-spacing:.3em">This is the free preview</div>
          <h2 style="position:static;font-size:46px;margin:18px 0 14px;color:{paper}">The full guideline is ready</h2>
          <p style="color:{paper};opacity:.8;font-size:16px;font-weight:300">Every section, every application page, no watermark. Unlock the complete document for 35 SAR at brand.sadaorg.com.</p>
        </div></div>"""

    def thanks():
        return f"""<div class="slide" style="background:{dark};display:grid;place-items:center">
        <div style="text-align:center">
          <img src="{logo_w}" style="max-height:130px;max-width:340px;object-fit:contain">
          <h1 style="color:{paper};font-size:60px;margin-top:26px">Thank you</h1>
          <div style="color:{accent};font-size:14px;letter-spacing:.2em;margin-top:8px" class="sora">{safe_name} · MADE AT BRAND.SADAORG.COM</div>
        </div></div>"""

    # ---- full deck ----
    full_slides = [cover(), contents(), div_slide("01", "Logo", "03"), logo_suite("04"),
                   div_slide("02", "Color", "05"), colors("06"),
                   div_slide("03", "Typography", "07"), typography("08"),
                   div_slide("04", "Applications", "09")]
    pg = 10
    for _, title, cap, img in mocks:
        full_slides.append(app_page(title, cap, img, "%02d" % pg)); pg += 1
    full_slides.append(thanks())

    # ---- preview: watermarked cover, contents, logo, colors, ONE application, unlock ----
    prev_slides = [cover(True), contents(True), logo_suite("03", True), colors("04", True)]
    if mocks:
        _, t, c2, img = mocks[0]
        prev_slides.append(app_page(t, c2, img, "05", True))
    prev_slides.append(unlock())

    out = {}
    kinds = (("preview", prev_slides),) if preview_only else (("full", full_slides), ("preview", prev_slides))
    for kind, slides in kinds:
        html = f"<!doctype html><html><head><meta charset='utf-8'><style>{css}</style></head><body>{''.join(slides)}</body></html>"
        hpath = os.path.join(out_dir, kind + ".html")
        with open(hpath, "w") as f:
            f.write(html)
        pdf = os.path.join(out_dir, kind + ".pdf")
        subprocess.run([CHROME, "--headless=new", "--no-sandbox", "--disable-gpu",
                        "--no-pdf-header-footer", "--virtual-time-budget=20000",
                        "--print-to-pdf=" + pdf, hpath],
                       check=True, timeout=120, capture_output=True)
        os.remove(hpath)
        out[kind] = pdf
    return out
