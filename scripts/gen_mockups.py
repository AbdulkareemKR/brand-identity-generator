"""
Generate real brand mockups with AI. GPT ONLY (no Gemini). Publishable template:
edit the CONFIG block for your brand, then run `python3 gen_mockups.py`.

Uses ONE key, the OpenAI / GPT image model `gpt-image-1`:
  OPENAI_API_KEY   (or NETZERO_OPENAI_API_KEY for Netzero billing)

Two GPT endpoints, picked automatically:
  /v1/images/edits         logo-bearing product mockups. Pass the REAL logo PNG(s)
                           as reference images so the model composites your mark
                           instead of redrawing letters. input_fidelity=high keeps
                           the mark and any faces sharp.
  /v1/images/generations   neutral vector art: patterns, spot icons, lifestyle scenes.

Best practices baked in:
  - Pass the REAL logo PNG as a reference so the model keeps it, does not redraw it.
  - input_fidelity="high" on every logo-bearing edit (best mark preservation).
  - "Absolutely NO text" guard so the model does not invent garbled foreign letters.
  - One product per entry, and several ANGLES per product (front / back / detail / stack).
  - Files land in OUT as PNG; optimize to JPG q85 afterwards (see bottom helper).

Stdlib only (urllib + ssl). No pip install needed to call the API.
"""
import os, json, base64, urllib.request, ssl, time, mimetypes

# ------------------------- CONFIG (edit per brand) -------------------------
BASE   = os.environ.get("BRAND_DIR", os.getcwd())   # project dir; assets + output live under it
OUT    = os.path.join(BASE, "mockups")
ASSETS = os.path.join(BASE, "assets")

# Model + billing. NETZERO_OPENAI_API_KEY wins if present (keeps Netzero billing separate).
MODEL   = os.environ.get("IMAGE_MODEL", "gpt-image-1")
QUALITY = os.environ.get("IMAGE_QUALITY", "high")     # low | medium | high | auto
API_KEY = os.environ.get("NETZERO_OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")

# Logo asset PNGs (produce these first with process_logo.py). Set to None if absent.
LOGO_NAVY  = os.path.join(ASSETS, "logo-navy.png")   # ink/dark wordmark on transparent
LOGO_WHITE = os.path.join(ASSETS, "logo-white.png")  # white wordmark for dark backgrounds
MARK       = os.path.join(ASSETS, "mark-navy.png")   # square symbol, ink
MARK_WHITE = os.path.join(ASSETS, "mark-white.png")  # square symbol, white
BADGE      = os.path.join(ASSETS, "app-badge.png")   # mark on rounded square, primary color

# One line brand description + exact palette. Keep hexes literal. (Netzero reference brand.)
PAL = ("Brand Netzero, a climate technology company that verifies reforestation with AI. "
       "Palette: primary green #35CA66, deep teal #003038, mint #E9F8EB, ink #232323, white #FFFFFF, "
       "accent lime #AEFF00, accent magenta #FF1991. "
       "Aesthetic: natural, contemporary, friendly, clean, optimistic, precise. "
       "Soft daylight, no people, mint or white background. ")

# Guards prepended to every logo-bearing prompt.
LOGO_RULE = ("Use the PROVIDED logo image EXACTLY as given, letter for letter, do NOT redraw, "
             "restyle, recolor, crop or add letters to it; every glyph and the mark's counter "
             "shapes must survive intact. Apply it printed / embroidered / foil stamped so it "
             "sits into the material and follows the surface curvature, folds and lighting, "
             "not a flat sticker. Keep the whole logo fully visible with clear space around it, "
             "never touching edges or handles. ")
NO_TEXT   = ("Absolutely NO text, letters or numbers anywhere except the provided logo. "
             "Flat solid brand colors, no gradients on the logo. Photographic, shot on a DSLR. ")
# QA-learned: blind emboss/letterpress at large scale garbles letterforms — business cards use
# flat 2 color print. App icons use the BADGE/mark only, never the wordmark.

# Logo-bearing mockups: (name, prompt, [reference PNGs], size). One product each; vary the angle.
# size: "1024x1024" | "1536x1024" (landscape) | "1024x1536" (portrait) | "auto".
EDIT_JOBS = [
    ("bc_front",   "A single business card FRONT, top-down flat lay on mint: a deep teal card with the white logo FLAT PRINTED at modest size centered (no emboss, no letterpress), rounded corners, soft daylight shadow.", [LOGO_WHITE], "1536x1024"),
    ("bc_back",    "A single business card BACK, top-down flat lay on mint: a white card with the small green mark flat printed in a corner and a faint dotted grid, soft shadow.", [MARK], "1536x1024"),
    ("bc_stack",   "An angled three quarter STACK of deep teal business cards with one white card fanned on top, logos flat printed, on mint, soft directional shadow.", [LOGO_WHITE, MARK], "1536x1024"),
    ("cup_mug",    "A white ceramic MUG, front view on mint, the green logo printed centered on the visible face, fully inside the face with clear space on both sides, not touching the handle, curving naturally with the ceramic, soft studio shadow.", [LOGO_NAVY], "1024x1024"),
    ("cup_takeaway","A white takeaway PAPER CUP with a green patterned sleeve, three quarter angle, the mark on the sleeve, mint background.", [MARK], "1024x1024"),
    ("tote",       "A natural cotton TOTE bag hanging, front view on mint, the green logo printed on the body, soft daylight.", [LOGO_NAVY], "1024x1536"),
    ("notebook",   "A deep teal hardcover NOTEBOOK with the mark foil stamped, plus a mint notebook and a pen, top-down on mint, soft shadow.", [MARK_WHITE], "1536x1024"),
    ("tshirt_front","FRONT of a white t-shirt on an invisible ghost mannequin, no person, empty, the green mark embroidered on the chest, mint background.", [MARK], "1024x1536"),
    ("polo_front", "FRONT of a deep teal polo shirt on an invisible ghost mannequin, no person, empty, the white mark embroidered on the chest, mint background.", [MARK_WHITE], "1024x1536"),
    ("cap",        "A deep teal baseball CAP, three quarter front, the green mark embroidered on the front panel, mint background, soft light.", [MARK], "1024x1024"),
    ("app_icon",   "A clean isolated flat APP ICON reproducing the provided rounded square badge exactly: solid brand color square, the symbol centered, NO wordmark, no 3D, no texture, no background plate, no gray tile, transparent background.", [BADGE], "1024x1024"),
    ("bottle",     "A matte deep teal reusable water BOTTLE, front view on mint, the white mark printed mid-body, soft daylight shadow.", [MARK_WHITE], "1024x1536"),
    ("giftbox",    "A closed deep teal rigid GIFT BOX with a mint ribbon, three quarter view on mint, the mark foil stamped on the lid, soft shadow.", [MARK_WHITE], "1536x1024"),
    ("lanyard",    "A green LANYARD with a blank white ID card holder, the mark at the top of the lanyard strap, on mint, soft light.", [MARK], "1024x1536"),
    ("signage",    "A modern office reception WALL sign, brushed white letters area, the green logo mounted on a warm concrete wall, bright daylight, photographic.", [LOGO_NAVY], "1536x1024"),
    ("storefront", "A bright modern STOREFRONT on a sunny green-lined street, the green logo above the entrance, glass facade, daytime, photographic, no people.", [LOGO_NAVY], "1536x1024"),
    ("billboard",  "A large outdoor BILLBOARD by a sunny modern street at daytime, a mint panel with the green logo centered and a thin dotted leaf grid, photographic.", [LOGO_NAVY], "1536x1024"),
]

# Neutral vector art (no logo): (name, prompt, size).
GEN_JOBS = [
    ("pattern", "Seamless tileable flat vector pattern: scattered thin line leaves, small plus marks, dotted grids and gentle contour waves in green #35CA66 and deep teal #003038 on mint #E9F8EB. Minimal, evenly spaced, no text.", "1024x1024"),
    ("spots",   "A neat row of six minimal line ICON spot illustrations in deep teal with green accents on mint: a leaf, a tree, a satellite, a water drop, a bar chart, a shield. 2px stroke, rounded, no text.", "1536x1024"),
    ("hero",    PAL + "Full bleed lifestyle key visual: a young reforestation nursery of small green saplings in warm morning light, soft depth of field, editorial, optimistic, no people, no text.", "1536x1024"),
]
# --------------------------------------------------------------------------

os.makedirs(OUT, exist_ok=True)
ctx = ssl.create_default_context()


def _multipart(fields, files):
    """Build a multipart/form-data body. fields: list[(name,value)]. files: list[(name,path)]."""
    boundary = "----brandid" + base64.urlsafe_b64encode(os.urandom(12)).decode().rstrip("=")
    nl = b"\r\n"
    buf = []
    for name, value in fields:
        buf.append(b"--" + boundary.encode() + nl)
        buf.append(('Content-Disposition: form-data; name="%s"' % name).encode() + nl + nl)
        buf.append(str(value).encode() + nl)
    for name, path in files:
        fn = os.path.basename(path)
        ctype = mimetypes.guess_type(fn)[0] or "application/octet-stream"
        with open(path, "rb") as f:
            data = f.read()
        buf.append(b"--" + boundary.encode() + nl)
        buf.append(('Content-Disposition: form-data; name="%s"; filename="%s"' % (name, fn)).encode() + nl)
        buf.append(("Content-Type: %s" % ctype).encode() + nl + nl)
        buf.append(data + nl)
    buf.append(b"--" + boundary.encode() + b"--" + nl)
    return b"".join(buf), "multipart/form-data; boundary=" + boundary


def save(n, d):
    with open(os.path.join(OUT, n + ".png"), "wb") as f:
        f.write(base64.b64decode(d))
    print("saved", n, flush=True)


def _post(url, data, headers, timeout):
    req = urllib.request.Request(url, data=data, headers=headers)
    return json.load(urllib.request.urlopen(req, context=ctx, timeout=timeout))


def edit(n, prompt, refs, size="1024x1024", tries=3):
    """Logo-bearing mockup via gpt-image-1 image edits (references composited in)."""
    if os.path.exists(os.path.join(OUT, n + ".png")):
        print("skip", n); return True
    if not API_KEY:
        print("no OPENAI_API_KEY, skip", n); return False
    refs = [r for r in refs if r and os.path.exists(r)]
    if not refs:
        print("no reference PNG for", n, "- falling back to generation"); return generate(n, LOGO_RULE + NO_TEXT + PAL + prompt, size, tries)
    fields = [("model", MODEL), ("prompt", LOGO_RULE + NO_TEXT + PAL + prompt),
              ("size", size), ("quality", QUALITY), ("input_fidelity", "high"), ("n", "1")]
    if n == "app_icon":
        fields.append(("background", "transparent"))
    files = [("image[]", r) for r in refs]
    body, ctype = _multipart(fields, files)
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": ctype, "Content-Length": str(len(body))}
    for t in range(tries):
        try:
            r = _post("https://api.openai.com/v1/images/edits", body, headers, 300)
            save(n, r["data"][0]["b64_json"]); return True
        except Exception as e:
            print("edit retry", n, t, repr(e)[:160], flush=True); time.sleep(4)
    return False


def generate(n, prompt, size="1024x1024", tries=2):
    """Neutral art via gpt-image-1 generations (no reference)."""
    if os.path.exists(os.path.join(OUT, n + ".png")):
        print("skip", n); return True
    if not API_KEY:
        print("no OPENAI_API_KEY, skip", n); return False
    body = json.dumps({"model": MODEL, "prompt": prompt, "size": size,
                       "quality": QUALITY, "n": 1}).encode()
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}
    for t in range(tries):
        try:
            r = _post("https://api.openai.com/v1/images/generations", body, headers, 300)
            save(n, r["data"][0]["b64_json"]); return True
        except Exception as e:
            print("generate retry", n, t, repr(e)[:160], flush=True); time.sleep(4)
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
    for n, p, refs, sz in EDIT_JOBS:
        edit(n, p, refs, sz)
    for n, p, sz in GEN_JOBS:
        generate(n, p, sz)
    optimize()
    print("DONE", flush=True)
