"""
Mode B helper: turn a PROVIDED logo PNG into the clean, reusable assets the deck
needs, and sample its palette. PIL only.

    python3 process_logo.py path/to/logo.png [--out assets] [--mark-run last] [--primary "#35CA66"]

Produces in --out:
    logo-navy.png    the source, trimmed to content (kept exactly as given)
    logo-white.png   every opaque pixel recolored white (for dark / primary backgrounds)
    mark-navy.png    the isolated SYMBOL, cropped to its own column run, padded square
    mark-white.png   white version of the mark
    app-badge.png    the white mark centered on a rounded square in the primary color
    palette.json     the sampled palette + the list of files written (machine readable)
And prints the top palette colors sampled from the logo.

This same module is imported by the web extraction backend (extract_service.py),
so keep it importable and side-effect free at import time.

Notes / best practices:
    - The mark is isolated by scanning columns that contain ink and taking one run
      (default the last / rightmost run, common for "WORDMARK  <symbol>" lockups).
      If it grabs a stray letter, change --mark-run (first | last | <index>) and rerun.
    - ALWAYS eyeball the outputs before wiring them in. A too-wide crop grabs a
      neighbor glyph; re-crop until the mark stands alone.
"""
import sys, os, json, argparse
from collections import Counter
from PIL import Image, ImageDraw


def load_rgba(p):
    im = Image.open(p).convert("RGBA")
    return im


def alpha_or_luma_mask(im, thr=24):
    """Opaque pixels; if the image is fully opaque, treat non-near-white as ink."""
    px = im.load()
    w, h = im.size
    a_max = max(px[x, y][3] for x in range(0, w, 4) for y in range(0, h, 4))
    mask = Image.new("1", (w, h), 0)
    mp = mask.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if a_max > 250:  # no real alpha -> use luminance vs white paper
                ink = (r + g + b) / 3 < 245
            else:
                ink = a > thr
            if ink:
                mp[x, y] = 1
    return mask


def content_bbox(mask):
    return mask.getbbox()


def column_runs(mask, gap=6):
    """Return list of (x0, x1) runs of columns that contain ink, merging small gaps."""
    w, h = mask.size
    mp = mask.load()
    cols = []
    for x in range(w):
        on = any(mp[x, y] for y in range(h))
        cols.append(on)
    runs, start = [], None
    blanks = 0
    for x in range(w):
        if cols[x]:
            if start is None:
                start = x
            blanks = 0
        else:
            if start is not None:
                blanks += 1
                if blanks > gap:
                    runs.append((start, x - blanks)); start = None
    if start is not None:
        runs.append((start, w - 1))
    return runs


def recolor_white(im):
    px = im.load(); w, h = im.size
    # does the source carry real transparency? sample alpha
    a_min = min(px[x, y][3] for x in range(0, w, 4) for y in range(0, h, 4))
    has_alpha = a_min < 250
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            if has_alpha:
                na = a
            else:
                # fully opaque source (white paper background): white pixels become
                # transparent, ink pixels become the white mark
                na = 0 if (r + g + b) / 3 > 245 else 255
            op[x, y] = (255, 255, 255, na)
    return out


def pad_square(im, bg=(0, 0, 0, 0)):
    w, h = im.size; s = max(w, h)
    out = Image.new("RGBA", (s, s), bg)
    out.paste(im, ((s - w) // 2, (s - h) // 2), im)
    return out


def sample_palette(im, k=5):
    """Cluster-based palette: merge similar shades into one swatch each instead of
    returning six near-duplicates, and put the saturated hero color first."""
    small = im.convert("RGBA").resize((128, 128))
    px = small.load(); c = Counter()
    for y in range(128):
        for x in range(128):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            if max(r, g, b) - min(r, g, b) < 12 and (r > 235 or r < 20):
                continue  # skip near white / near black neutrals
            c[(r // 8 * 8, g // 8 * 8, b // 8 * 8)] += 1
    # greedy clustering: frequent colors absorb anything within a small distance
    clusters = []  # [sum_r, sum_g, sum_b, weight]
    for (r, g, b), n in c.most_common(400):
        placed = False
        for cl in clusters:
            cr, cg, cb = cl[0] / cl[3], cl[1] / cl[3], cl[2] / cl[3]
            if ((r - cr) ** 2 + (g - cg) ** 2 + (b - cb) ** 2) ** 0.5 < 60:
                cl[0] += r * n; cl[1] += g * n; cl[2] += b * n; cl[3] += n
                placed = True
                break
        if not placed:
            clusters.append([r * n, g * n, b * n, n])
    total = sum(cl[3] for cl in clusters) or 1
    out = []
    for cl in sorted(clusters, key=lambda cl: -cl[3]):
        if cl[3] / total < 0.02 and len(out) >= 2:
            continue  # drop anti-aliasing noise once real colors exist
        r, g, b = (round(cl[i] / cl[3]) for i in (0, 1, 2))
        out.append((r, g, b, cl[3]))
        if len(out) == k:
            break
    # the brand hero leads: promote the most frequent clearly saturated cluster
    for i, (r, g, b, n) in enumerate(out):
        if max(r, g, b) - min(r, g, b) >= 50:
            out.insert(0, out.pop(i))
            break
    return ["#%02X%02X%02X" % (r, g, b) for r, g, b, _ in out]


def parse_hex(s):
    s = s.strip().lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))


def pick_primary(palette):
    """Most saturated, non neutral swatch = the brand primary (for the app badge)."""
    best, best_sat = None, -1
    for h in palette:
        r, g, b = parse_hex(h)
        sat = max(r, g, b) - min(r, g, b)
        if sat > best_sat:
            best, best_sat = (r, g, b), sat
    return best or (35, 202, 102)


def app_badge(mark_white, primary, size=512, radius_ratio=0.22, mark_ratio=0.6):
    """White mark centered on a rounded square in the primary color. No extra plate."""
    r, g, b = primary
    badge = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    rad = int(size * radius_ratio)
    plate = Image.new("RGBA", (size, size), (0, 0, 0, 0))
    ImageDraw.Draw(plate).rounded_rectangle([0, 0, size - 1, size - 1], radius=rad,
                                            fill=(r, g, b, 255))
    badge.alpha_composite(plate)
    m = mark_white.copy()
    mw = int(size * mark_ratio)
    m = m.resize((mw, round(m.height * mw / m.width)), Image.LANCZOS)
    badge.alpha_composite(m, ((size - m.width) // 2, (size - m.height) // 2))
    return badge


def process(logo_path, out="assets", mark_run="last", primary=None):
    """Turn a provided logo into clean assets + a sampled palette.
    Returns a dict describing what was written. Reused by the web backend."""
    os.makedirs(out, exist_ok=True)
    im = load_rgba(logo_path)
    mask = alpha_or_luma_mask(im)
    bbox = content_bbox(mask)
    if bbox:
        im = im.crop(bbox); mask = mask.crop(bbox)

    written = {}
    im.save(os.path.join(out, "logo-navy.png")); written["logo"] = "logo-navy.png"
    recolor_white(im).save(os.path.join(out, "logo-white.png")); written["logo_white"] = "logo-white.png"

    mark_white_img = None
    runs = column_runs(mask)
    note = ""
    if runs:
        if mark_run == "last":
            r = runs[-1]
        elif mark_run == "first":
            r = runs[0]
        else:
            r = runs[int(mark_run)]
        pad = 4
        crop = im.crop((max(0, r[0] - pad), 0, min(im.size[0], r[1] + 1 + pad), im.size[1]))
        cm = alpha_or_luma_mask(crop)
        vb = cm.getbbox()
        if vb:
            crop = crop.crop(vb)
        sq = pad_square(crop)
        sq.save(os.path.join(out, "mark-navy.png")); written["mark"] = "mark-navy.png"
        mark_white_img = recolor_white(sq)
        mark_white_img.save(os.path.join(out, "mark-white.png")); written["mark_white"] = "mark-white.png"
        note = "mark from run %s of %d runs; if wrong, try --mark-run first|<index>" % (r, len(runs))
    else:
        note = "no column runs found; check the source image"

    palette = sample_palette(im)
    prim = parse_hex(primary) if primary else pick_primary(palette)
    if mark_white_img is not None:
        app_badge(mark_white_img, prim).save(os.path.join(out, "app-badge.png"))
        written["app_badge"] = "app-badge.png"

    meta = {"palette": palette, "primary": "#%02X%02X%02X" % prim, "files": written, "note": note}
    with open(os.path.join(out, "palette.json"), "w") as f:
        json.dump(meta, f, indent=2)
    return meta


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logo")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--mark-run", default="last", help="last | first | <index>")
    ap.add_argument("--primary", default=None, help="badge color hex, e.g. #35CA66; default = most saturated sampled swatch")
    a = ap.parse_args()

    meta = process(a.logo, a.out, a.mark_run, a.primary)
    print(meta["note"])
    print("palette:", ", ".join(meta["palette"]), "| primary", meta["primary"])
    print("wrote assets to", a.out, "->", ", ".join(meta["files"].values()))


if __name__ == "__main__":
    main()
