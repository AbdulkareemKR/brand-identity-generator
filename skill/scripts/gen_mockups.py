"""
Generate real brand mockups with AI. Publishable template: edit the CONFIG block
for your brand, then run `python3 gen_mockups.py`.

Needs env keys (whichever engines you use):
  GEMINI_API_KEY   -> logo-bearing product mockups (pass the real logo as a reference)
  OPENAI_API_KEY   -> flat vector illustrations, seamless patterns, illustrated scenes

Best practices baked in:
  - Pass the REAL logo PNG so Gemini composites it instead of redrawing letters.
  - "Absolutely NO text" guard so the model does not invent garbled foreign letters.
  - One product per entry, and several ANGLES per product (front / back / detail / stack).
  - Files land in OUT as PNG; optimize to JPG q85 afterwards (see bottom helper).
"""
import os, json, base64, urllib.request, ssl, time

# ------------------------- CONFIG (edit per brand) -------------------------
BASE   = os.environ.get("BRAND_DIR", os.getcwd())   # project dir; assets + output live under it
OUT    = os.path.join(BASE, "mockups")
ASSETS = os.path.join(BASE, "assets")
# Logo asset PNGs (produce these first, e.g. with process_logo.py). Set to None if absent.
LOGO_NAVY  = os.path.join(ASSETS, "logo-navy.png")   # ink/dark wordmark on transparent
LOGO_WHITE = os.path.join(ASSETS, "logo-white.png")  # white wordmark for dark backgrounds
MARK       = os.path.join(ASSETS, "mark-navy.png")   # square symbol, ink
MARK_WHITE = os.path.join(ASSETS, "mark-white.png")  # square symbol, white

# One line brand description + exact palette. Keep hexes literal.
PAL = ("Brand ACME, a premium studio. Palette: navy #1F2A44, sand #DBC3A5, cream #F4EFE6, "
       "stone gray #6B6F76. Aesthetic: minimal, calm, premium, geometric. "
       "Soft studio light, no people, cream background. ")

# Guards prepended to every logo-bearing prompt.
LOGO_RULE = "Use the PROVIDED logo image EXACTLY as given, do NOT redraw or alter its letters or mark. "
NO_TEXT   = "Absolutely NO text, letters or numbers anywhere except the provided logo. "

# Logo-bearing mockups: (name, prompt, [reference PNGs]). One product each; vary the angle.
GEMINI_JOBS = [
    ("bc_front",  "Single business card top-down flat lay on cream: the NAVY card FRONT with the white logo centered, rounded corners, soft shadow.", [LOGO_WHITE]),
    ("bc_back",   "Single business card top-down flat lay on cream: the CREAM card BACK with the small navy mark in a corner and a faint dotted grid, soft shadow.", [MARK]),
    ("bc_stack",  "Angled three quarter stack of navy business cards with one cream card fanned on top, on cream, soft directional shadow.", [LOGO_NAVY, MARK]),
    ("cup_front", "A white paper coffee cup front view on cream, the navy logo and a thin line motif, soft studio shadow.", [LOGO_NAVY]),
    ("cup_angle", "The same paper cup at a three quarter side angle showing the motif wrapping around, soft shadow.", [LOGO_NAVY]),
    ("vest_front","Front of a navy staff vest on an invisible ghost mannequin, no person, the mark embroidered on the chest, cream background.", [MARK_WHITE]),
    ("vest_back", "Back of the same navy vest on an invisible ghost mannequin, no person, a small mark at the nape, cream background.", [MARK_WHITE]),
    ("app_icon",  "A navy rounded square app icon featuring the white mark centered, clean and isolated on cream, no background plate or gray tile, soft reflection.", [MARK_WHITE]),
    ("notebook",  "A navy hardcover notebook with the sand logo debossed, plus a cream notebook and a pen, top-down on cream, soft shadow.", [LOGO_NAVY]),
    ("billboard", "A large outdoor billboard by a modern street at dusk, navy panel with the white logo centered and a thin dotted grid, photographic.", [LOGO_WHITE]),
]

# Neutral vector art (no logo): (name, prompt, size).
OPENAI_JOBS = [
    ("pattern", "Seamless tileable flat vector pattern: scattered thin line circles, small plus marks, dotted grids and gentle waves in navy #1F2A44 and sand #DBC3A5 on cream #F4EFE6. Minimal, evenly spaced, no text.", "1024x1024"),
    ("spots",   "A neat row of six minimal line icon spot illustrations in navy with sand accents on cream: code brackets, link, bar chart, people, rocket, shield. 2px stroke, rounded, no text.", "1536x1024"),
    ("hero",    PAL + "Full bleed lifestyle key visual: a calm modern tech workspace corner, warm cream walls, geometric wall art, soft daylight, editorial, no people, no text.", "1536x1024"),
]
# --------------------------------------------------------------------------

os.makedirs(OUT, exist_ok=True)
ctx = ssl.create_default_context()

def b64(p):
    with open(p, "rb") as f:
        return base64.b64encode(f.read()).decode()

def save(n, d):
    with open(os.path.join(OUT, n + ".png"), "wb") as f:
        f.write(base64.b64decode(d))
    print("saved", n, flush=True)

def gemini(n, prompt, refs, tries=3):
    if os.path.exists(os.path.join(OUT, n + ".png")):
        print("skip", n); return True
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        print("no GEMINI_API_KEY, skip", n); return False
    refs = [r for r in refs if r and os.path.exists(r)]
    parts = [{"inline_data": {"mime_type": "image/png", "data": b64(r)}} for r in refs]
    parts.append({"text": LOGO_RULE + NO_TEXT + PAL + prompt})
    url = ("https://generativelanguage.googleapis.com/v1beta/models/"
           "gemini-2.5-flash-image:generateContent?key=" + key)
    body = json.dumps({"contents": [{"parts": parts}]}).encode()
    for t in range(tries):
        try:
            req = urllib.request.Request(url, data=body, headers={"Content-Type": "application/json"})
            r = json.load(urllib.request.urlopen(req, context=ctx, timeout=240))
            for p in r["candidates"][0]["content"]["parts"]:
                if "inlineData" in p:
                    save(n, p["inlineData"]["data"]); return True
            print("noimg", n, flush=True)
        except Exception as e:
            print("gemini retry", n, t, repr(e)[:120], flush=True); time.sleep(3)
    return False

def openai(n, prompt, size="1024x1024", tries=2):
    if os.path.exists(os.path.join(OUT, n + ".png")):
        print("skip", n); return True
    key = os.environ.get("OPENAI_API_KEY")
    if not key:
        print("no OPENAI_API_KEY, skip", n); return False
    for t in range(tries):
        try:
            body = json.dumps({"model": "gpt-image-1", "prompt": prompt,
                               "size": size, "quality": "high", "n": 1}).encode()
            req = urllib.request.Request("https://api.openai.com/v1/images/generations", data=body,
                headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"})
            save(n, json.load(urllib.request.urlopen(req, context=ctx, timeout=300))["data"][0]["b64_json"])
            return True
        except Exception as e:
            print("openai retry", n, t, repr(e)[:140], flush=True); time.sleep(4)
    return False

def optimize(max_w=1600, q=85):
    """PNG -> JPG q85 progressive, downscaled. Keeps logos/marks as PNG (call only on mockups)."""
    try:
        from PIL import Image
    except ImportError:
        print("PIL missing, skip optimize"); return
    for fn in os.listdir(OUT):
        if not fn.endswith(".png"):
            continue
        p = os.path.join(OUT, fn)
        im = Image.open(p).convert("RGB")
        if im.width > max_w:
            im = im.resize((max_w, round(im.height * max_w / im.width)), Image.LANCZOS)
        im.save(p[:-4] + ".jpg", "JPEG", quality=q, optimize=True, progressive=True)
    print("optimized mockups to JPG", flush=True)

if __name__ == "__main__":
    for n, p, refs in GEMINI_JOBS:
        gemini(n, p, refs)
    for n, p, sz in OPENAI_JOBS:
        openai(n, p, sz)
    optimize()
    print("DONE", flush=True)
