"""
Mode B helper: turn a PROVIDED logo PNG into the clean, reusable assets the deck
needs, and sample its palette. PIL only.

    python3 process_logo.py path/to/logo.png [--out assets] [--mark-run last]

Produces in --out:
    logo-navy.png    the source, trimmed to content (kept exactly as given)
    logo-white.png   every opaque pixel recolored white (for dark / primary backgrounds)
    mark-navy.png    the isolated SYMBOL, cropped to its own column run, padded square
    mark-white.png   white version of the mark
And prints the top palette colors sampled from the logo.

Notes / best practices:
    - The mark is isolated by scanning columns that contain ink and taking one run
      (default the last / rightmost run, common for "WORDMARK  <symbol>" lockups).
      If it grabs a stray letter, change --mark-run (first | last | <index>) and rerun.
    - ALWAYS eyeball the outputs before wiring them in. A too-wide crop grabs a
      neighbor glyph; re-crop until the mark stands alone.
"""
import sys, os, argparse
from collections import Counter
from PIL import Image


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
    out = Image.new("RGBA", (w, h), (0, 0, 0, 0)); op = out.load()
    for y in range(h):
        for x in range(w):
            r, g, b, a = px[x, y]
            op[x, y] = (255, 255, 255, a if a > 0 else (0 if (r + g + b) / 3 > 245 else 255))
    return out


def pad_square(im, bg=(0, 0, 0, 0)):
    w, h = im.size; s = max(w, h)
    out = Image.new("RGBA", (s, s), bg)
    out.paste(im, ((s - w) // 2, (s - h) // 2), im)
    return out


def sample_palette(im, k=6):
    small = im.convert("RGBA").resize((80, 80))
    px = small.load(); c = Counter()
    for y in range(80):
        for x in range(80):
            r, g, b, a = px[x, y]
            if a < 40:
                continue
            if max(r, g, b) - min(r, g, b) < 12 and (r > 235 or r < 20):
                continue  # skip near white / near black neutrals
            c[(r // 16 * 16, g // 16 * 16, b // 16 * 16)] += 1
    return ["#%02X%02X%02X" % rgb for rgb, _ in c.most_common(k)]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("logo")
    ap.add_argument("--out", default="assets")
    ap.add_argument("--mark-run", default="last", help="last | first | <index>")
    a = ap.parse_args()
    os.makedirs(a.out, exist_ok=True)

    im = load_rgba(a.logo)
    mask = alpha_or_luma_mask(im)
    bbox = content_bbox(mask)
    if bbox:
        im = im.crop(bbox); mask = mask.crop(bbox)

    im.save(os.path.join(a.out, "logo-navy.png"))
    recolor_white(im).save(os.path.join(a.out, "logo-white.png"))

    runs = column_runs(mask)
    if runs:
        if a.mark_run == "last":
            r = runs[-1]
        elif a.mark_run == "first":
            r = runs[0]
        else:
            r = runs[int(a.mark_run)]
        pad = 4
        crop = im.crop((max(0, r[0] - pad), 0, min(im.size[0], r[1] + 1 + pad), im.size[1]))
        # tighten vertically
        cm = alpha_or_luma_mask(crop)
        vb = cm.getbbox()
        if vb:
            crop = crop.crop(vb)
        sq = pad_square(crop)
        sq.save(os.path.join(a.out, "mark-navy.png"))
        recolor_white(sq).save(os.path.join(a.out, "mark-white.png"))
        print("mark from run", r, "of", len(runs), "runs; if wrong, try --mark-run first|<index>")
    else:
        print("no column runs found; check the source image")

    print("palette:", ", ".join(sample_palette(im)))
    print("wrote assets to", a.out)


if __name__ == "__main__":
    main()
