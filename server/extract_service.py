"""
Brand Identity Generator — extraction + generation backend (brand.sadaorg.com).

Flow A (has a logo):
  POST /api/extract     multipart "logo" (+optional "primary" hex). Extracts clean
                        variants + palette with process_logo. Returns previews,
                        palette and a pack_id.
  POST /api/generate    {"mode":"logo","pack_id":..., "palette":[hex...], "name":...}
                        Kicks an async job: gpt-image-1 mockups with the REAL mark
                        composited (images/edits, input_fidelity high).

Flow B (no logo yet):
  POST /api/generate    {"mode":"scratch","name":...,"desc":...,"style":...,
                         "palette":[hex...]}  -> 6 logo concepts (images/generations).
  POST /api/generate    {"mode":"logo","concept":"<job>/<file>", ...} to build the
                        mockup set around a picked concept.

Shared:
  GET /api/job/<id>          job status: {status, done, total, items:[{name,url}]}
  GET /api/file/<id>/<name>  a generated image
  GET /api/pack/<id>.zip     zip of everything the job/extraction produced
  GET /api/health

Money guards: quality medium, max 8 images per job, 4 jobs per IP per hour.
Needs OPENAI_API_KEY in env (gpt-image-1). PIL for extraction/compositing.
"""
import os, io, re, json, uuid, base64, tempfile, time, threading, zipfile, mimetypes
import urllib.request, ssl, hmac, hashlib
from collections import deque
from flask import Flask, request, jsonify, send_file, abort
from PIL import Image, UnidentifiedImageError
import process_logo
import deck_builder

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 10 * 1024 * 1024  # 10 MB upload cap

DATA_DIR = os.environ.get("BRAND_DATA", os.path.join(tempfile.gettempdir(), "brandpacks"))
os.makedirs(DATA_DIR, exist_ok=True)
PACK_TTL = 24 * 3600
ALLOWED = {"image/png", "image/jpeg", "image/webp"}
PREVIEW_ORDER = ["logo", "logo_white", "mark", "mark_white", "app_badge"]

API_KEY = os.environ.get("OPENAI_API_KEY")
MODEL = os.environ.get("IMAGE_MODEL", "gpt-image-1")
QUALITY = os.environ.get("IMAGE_QUALITY", "medium")
MOYASAR_SK = os.environ.get("MOYASAR_SK")            # secret key, payment verification
PRICE_HALALAS = int(os.environ.get("PRICE_HALALAS", "3500"))   # 35 SAR
MAX_JOB_IMAGES = 8
RATE_LIMIT = 4            # generate jobs per IP
EXTRACT_LIMIT = 20        # extract calls per IP (cheaper, but disk+CPU)
RATE_WINDOW = 3600
# NOTE: in-memory jobs/rate require exactly ONE gunicorn worker (-w 1, threads ok).

HEX_RE = re.compile(r"^#[0-9a-fA-F]{6}$")
CTX = ssl.create_default_context()

jobs = {}                 # id -> {status, done, total, items, error, dir}
rate = {}                 # ip -> deque[timestamps]
lock = threading.Lock()

STYLES = {
    "minimal":    "ultra minimal flat vector mark, geometric, generous negative space, single weight lines",
    "modern":     "modern geometric flat vector logo, bold simple shapes, crisp edges, grid built",
    "organic":    "organic natural logo, flowing leaf and branch forms, soft curves, botanical",
    "playful":    "playful rounded logo, friendly bouncy shapes, thick rounded strokes, cheerful",
    "luxury":     "luxury logo, refined thin serif monogram feel, elegant, premium, restrained",
    "tech":       "futuristic tech logo, sharp angular mark, circuit and motion cues, precise",
    "vintage":    "vintage retro badge logo, classic emblem layout, subtle texture, timeless",
    "handdrawn":  "hand drawn logo, imperfect charming linework, artisanal, sketch quality",
    "mascot":     "friendly mascot character logo, simple cute character head, bold outlines",
    "monogram":   "monogram lettermark logo, interlocked initials, balanced strokes, iconic",
    "abstract":   "abstract gradient logo, fluid overlapping translucent shapes, contemporary",
    "calligraphy":"elegant Arabic calligraphy inspired logo, flowing strokes, modern diwani feel",
}


# ---------------------------------------------------------------- helpers
def _sweep():
    now = time.time()
    try:
        for fn in os.listdir(DATA_DIR):
            p = os.path.join(DATA_DIR, fn)
            if now - os.path.getmtime(p) > PACK_TTL:
                if os.path.isfile(p):
                    os.remove(p)
                else:
                    for r, ds, fs in os.walk(p, topdown=False):
                        for f in fs: os.remove(os.path.join(r, f))
                        for d in ds: os.rmdir(os.path.join(r, d))
                    os.rmdir(p)
    except OSError:
        pass
    # prune in-memory state too, or a long-lived process grows forever
    with lock:
        for jid in [j for j, v in jobs.items() if v.get("t0", 0) and now - v["t0"] > PACK_TTL]:
            jobs.pop(jid, None)
        for ip in [ip for ip, q in rate.items() if not q or now - q[-1] > RATE_WINDOW]:
            rate.pop(ip, None)


def _dataurl(path):
    with open(path, "rb") as f:
        return "data:image/png;base64," + base64.b64encode(f.read()).decode()


def _client_ip():
    # nginx overwrites X-Real-IP with $remote_addr (never pass-through), and the
    # app binds 127.0.0.1 only, so the header is trustworthy in this deployment.
    return request.headers.get("X-Real-IP") or request.remote_addr or "?"


def _rate_ok(ip, limit=RATE_LIMIT, bucket=""):
    with lock:
        q = rate.setdefault(bucket + ip, deque())
        now = time.time()
        while q and now - q[0] > RATE_WINDOW:
            q.popleft()
        if len(q) >= limit:
            return False
        q.append(now)
        return True


def _clean_palette(p):
    out = [h.upper() for h in (p or []) if isinstance(h, str) and HEX_RE.match(h)]
    return out[:6]


def _multipart(fields, files):
    boundary = "----brandid" + base64.urlsafe_b64encode(os.urandom(12)).decode().rstrip("=")
    nl = b"\r\n"; buf = []
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


def _post(url, data, headers, timeout=300):
    req = urllib.request.Request(url, data=data, headers=headers)
    return json.load(urllib.request.urlopen(req, context=CTX, timeout=timeout))


def gpt_edit(prompt, refs, size="1024x1024", transparent=False, tries=3):
    fields = [("model", MODEL), ("prompt", prompt), ("size", size),
              ("quality", QUALITY), ("input_fidelity", "high"), ("n", "1")]
    if transparent:
        fields.append(("background", "transparent"))
    body, ctype = _multipart(fields, [("image[]", r) for r in refs])
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": ctype,
               "Content-Length": str(len(body))}
    for t in range(tries):
        try:
            r = _post("https://api.openai.com/v1/images/edits", body, headers)
            return base64.b64decode(r["data"][0]["b64_json"])
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(4)


def gpt_generate(prompt, size="1024x1024", transparent=False, tries=3):
    payload = {"model": MODEL, "prompt": prompt, "size": size, "quality": QUALITY, "n": 1}
    if transparent:
        payload["background"] = "transparent"
    headers = {"Authorization": "Bearer " + API_KEY, "Content-Type": "application/json"}
    for t in range(tries):
        try:
            r = _post("https://api.openai.com/v1/images/generations", json.dumps(payload).encode(), headers)
            return base64.b64decode(r["data"][0]["b64_json"])
        except Exception:
            if t == tries - 1:
                raise
            time.sleep(4)


# ---------------------------------------------------------------- job engine
NO_TEXT = ("Absolutely NO text, letters or numbers anywhere except the provided logo. "
           "The logo in flat solid colors, no gradient. Photographic, shot on a DSLR. ")
LOGO_RULE = ("Use the PROVIDED logo image EXACTLY as given, letter for letter, do NOT redraw, "
             "restyle, recolor, crop or add letters to it; every glyph and counter shape must "
             "survive intact. Apply it printed or embroidered so it sits into the material and "
             "follows the surface curvature, folds and lighting, not a flat sticker. Keep the "
             "whole logo fully visible with clear space around it, never touching edges or handles. ")


def _mockup_jobs(assets, palette):
    """Mockup set for a brand with a real mark. assets = dict name->path (may miss some)."""
    hexes = ", ".join(palette[:4]) if palette else "#35CA66, #003038, #E9F8EB"
    pal = ("Brand palette: %s. Aesthetic: clean, contemporary, premium. "
           "Soft daylight, no people. " % hexes)
    mark = assets.get("mark") or assets.get("logo")
    mark_w = assets.get("mark_white") or assets.get("logo_white") or mark
    logo = assets.get("logo") or mark
    logo_w = assets.get("logo_white") or mark_w
    badge = assets.get("app_badge") or mark
    return [
        ("business_cards", "An angled three quarter stack of business cards in the darkest brand color with one light card fanned on top, the light logo FLAT PRINTED at modest size on the dark cards (no emboss, no letterpress, every letter visible), soft directional shadow, studio flat lay.", [logo_w], "1536x1024", False),
        ("mug",           "A white ceramic mug, front view, the logo printed centered on the visible face, entire logo fully visible with clear space on both sides, not touching the handle, curving naturally with the ceramic, soft studio shadow, light background tinted with the palest brand color.", [logo], "1024x1024", False),
        ("tshirt",        "Front of a white t-shirt on an invisible ghost mannequin, no person, empty, the mark embroidered on the chest, soft daylight, pale brand color background.", [mark], "1024x1536", False),
        ("tote",          "A natural cotton tote bag hanging, front view, the logo printed on the body, the ENTIRE printed logo fully visible inside the frame with generous margin, soft daylight, pale background.", [logo], "1024x1536", False),
        ("app_icon",      "A clean isolated flat app icon reproducing the provided rounded square badge EXACTLY: solid brand color square, symbol centered, NO wordmark, no 3D, no texture, no background plate, no gray tile.", [badge], "1024x1024", True),
        ("notebook",      "A hardcover notebook in the darkest brand color with the light mark foil stamped small, plus a pen, top-down studio flat lay, soft shadow.", [mark_w], "1536x1024", False),
        ("signage",       "A modern office reception wall sign, the logo as crisp CNC cut acrylic letters mounted on a warm light wall, every letterform and counter clean and unmelted, bright daylight, photographic.", [logo], "1536x1024", False),
        ("billboard",     "A large outdoor billboard by a sunny modern street at daytime, a light panel composed like a real ad: the logo upper center in its exact flat brand colors, an abstract accent color CTA pill shape lower right, a thin accent rule, NO invented words, photographic.", [logo], "1536x1024", False),
    ], pal


# Cost-aligned tiers: AI images are the expensive part. The free tier renders ONE
# teaser product; payment unlocks generation of the remaining seven + full deck.
TEASER = {"mug"}


def _run_logo_job(jid, assets, palette, name, full=False):
    job = jobs[jid]
    try:
        entries, pal = _mockup_jobs(assets, palette)
        entries = entries[:MAX_JOB_IMAGES]
        if not full:
            entries = [e for e in entries if e[0] in TEASER]
        else:
            # continuation after payment: skip anything already rendered
            entries = [e for e in entries if not os.path.exists(os.path.join(job["dir"], e[0] + ".png"))]
        job["total"] = len(entries)
        for fname, prompt, refs, size, transp in entries:
            try:
                refs = [r for r in refs if r and os.path.exists(r)]
                data = gpt_edit(LOGO_RULE + NO_TEXT + pal + prompt, refs, size, transp)
                out = os.path.join(job["dir"], fname + ".png")
                with open(out, "wb") as f:
                    f.write(data)
                job["items"].append({"name": fname, "url": "/api/file/%s/%s.png" % (jid, fname)})
            except Exception as e:
                job["items"].append({"name": fname, "error": repr(e)[:120]})
            job["done"] += 1
        # ship the source assets inside the kit zip too, so one download has everything
        adir = os.path.join(job["dir"], "assets")
        os.makedirs(adir, exist_ok=True)
        for k, p in assets.items():
            try:
                if not os.path.exists(os.path.join(adir, os.path.basename(p))):
                    with open(p, "rb") as src, open(os.path.join(adir, os.path.basename(p)), "wb") as dst:
                        dst.write(src.read())
            except OSError:
                pass
        # remember inputs so the paid continuation survives a restart
        with open(os.path.join(job["dir"], "meta.json"), "w") as f:
            json.dump({"name": name, "palette": palette}, f)
        # full.pdf must NOT land in the kit zip, so zip first, then build decks
        _zip_job(jid)
        try:
            deck_builder.build_deck(job["dir"], name, palette, preview_only=not full)
            job["deck"] = True
        except Exception as e:
            job["deck_error"] = repr(e)[:160]
        job["full"] = full
    finally:
        job["status"] = "done"
        _persist_job(jid)


def _dehaze(path):
    """Kill the glow/halo haze gpt-image-1 bakes into 'transparent' logo alpha:
    faint alpha becomes fully transparent, solid alpha stays."""
    try:
        im = Image.open(path).convert("RGBA")
        a = im.getchannel("A").point(lambda v: 0 if v < 90 else v)
        im.putalpha(a)
        im.save(path)
    except OSError:
        pass


def _run_scratch_job(jid, name, desc, style, palette):
    job = jobs[jid]
    try:
        hexes = ", ".join(palette[:4]) if palette else "#35CA66, #003038"
        styled = STYLES.get(style, STYLES["modern"])
        latin = all(ord(c) < 0x600 or not c.isalpha() for c in name)
        name_part = ('The logo includes the brand name "%s" spelled exactly, in clean matching lettering. ' % name) if (name and latin and len(name) <= 18) else "Symbol only, no lettering. "
        base = ("Professional logo design for a brand called %s. %s. Style: %s. "
                "Colors strictly and exactly from: %s. %s"
                "FLAT VECTOR with hard edges and solid fills only: absolutely no glow, no halo, "
                "no gradient, no soft shadow, no haze, no outline effects. "
                "Centered, no photo, no mockup, no background scene, no watermark. "
                % (name, desc, styled, hexes, name_part))
        # four genuinely different directions (kept lean: concepts are free tier)
        variations = [
            "Concept direction: a single iconic symbol drawn from the literal subject of the description. ",
            "Concept direction: an emblem or badge composition framing the name. ",
            "Concept direction: a monogram or lettermark built from the brand's initial letters. ",
            "Concept direction: a negative space trick hiding a second meaning. ",
        ]
        job["total"] = len(variations)
        for i, extra in enumerate(variations, 1):
            fname = "concept_%d" % i
            try:
                data = gpt_generate(base + extra, "1024x1024", transparent=True)
                p = os.path.join(job["dir"], fname + ".png")
                with open(p, "wb") as f:
                    f.write(data)
                _dehaze(p)
                job["items"].append({"name": fname, "url": "/api/file/%s/%s.png" % (jid, fname)})
            except Exception as e:
                job["items"].append({"name": fname, "error": repr(e)[:120]})
            job["done"] += 1
        _zip_job(jid)
    finally:
        job["status"] = "done"
        _persist_job(jid)


def _persist_job(jid):
    """Write terminal job state next to its files so downloads and status
    survive a process restart (the in-memory dict does not)."""
    j = jobs.get(jid)
    if not j:
        return
    try:
        with open(os.path.join(j["dir"], "status.json"), "w") as f:
            json.dump({"status": j["status"], "done": j["done"], "total": j["total"],
                       "items": j["items"], "full": bool(j.get("full")),
                       "deck": bool(j.get("deck")), "deck_error": j.get("deck_error")}, f)
    except OSError:
        pass


def _zip_job(jid):
    d = jobs[jid]["dir"]
    zpath = os.path.join(DATA_DIR, jid + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, fs in os.walk(d):
            for fn in sorted(fs):
                full = os.path.join(root, fn)
                z.write(full, arcname="brand-kit/" + os.path.relpath(full, d))


# ---------------------------------------------------------------- routes
@app.get("/api/health")
def health():
    return jsonify(ok=True, ai=bool(API_KEY))


@app.post("/api/extract")
def extract():
    _sweep()
    if not _rate_ok(_client_ip(), EXTRACT_LIMIT, "x:"):
        return jsonify(ok=False, error="Rate limit reached, try again in an hour."), 429
    f = request.files.get("logo")
    if not f or not f.filename:
        return jsonify(ok=False, error="No logo file uploaded. Send a PNG, JPG or WEBP in the 'logo' field."), 400
    if f.mimetype not in ALLOWED:
        return jsonify(ok=False, error="Unsupported type %s. Upload a PNG, JPG or WEBP. Export SVG to PNG first." % f.mimetype), 415
    raw = f.read()
    try:
        Image.open(io.BytesIO(raw)).verify()
    except (UnidentifiedImageError, OSError, ValueError):
        return jsonify(ok=False, error="That file is not a readable image."), 400

    primary = (request.form.get("primary") or "").strip() or None
    if primary and not HEX_RE.match(primary):
        primary = None
    pid = uuid.uuid4().hex
    pdir = os.path.join(DATA_DIR, pid)
    out = os.path.join(pdir, "assets")
    os.makedirs(out, exist_ok=True)
    src = os.path.join(pdir, "source.png")
    try:
        Image.open(io.BytesIO(raw)).convert("RGBA").save(src)
    except Exception:
        return jsonify(ok=False, error="Could not decode that image."), 400
    try:
        meta = process_logo.process(src, out=out, mark_run="last", primary=primary)
    except Exception as e:
        return jsonify(ok=False, error="Extraction failed: %s" % repr(e)[:200]), 500

    previews = {}
    for key in PREVIEW_ORDER:
        fn = meta["files"].get(key)
        if fn and os.path.exists(os.path.join(out, fn)):
            previews[key] = _dataurl(os.path.join(out, fn))

    zpath = os.path.join(DATA_DIR, pid + ".zip")
    with zipfile.ZipFile(zpath, "w", zipfile.ZIP_DEFLATED) as z:
        for fn in os.listdir(out):
            z.write(os.path.join(out, fn), arcname="brand-assets/" + fn)

    return jsonify(ok=True, pack_id=pid, palette=meta["palette"], primary=meta["primary"],
                   note=meta.get("note", ""), previews=previews,
                   download="/api/pack/%s.zip" % pid)


@app.post("/api/generate")
def generate():
    if not API_KEY:
        return jsonify(ok=False, error="AI generation is not configured on this server."), 503
    body = request.get_json(silent=True) or {}
    mode = body.get("mode")
    palette = _clean_palette(body.get("palette"))
    name = str(body.get("name") or "the brand")[:60]

    jid = uuid.uuid4().hex
    jdir = os.path.join(DATA_DIR, jid)
    os.makedirs(jdir, exist_ok=True)
    jobs[jid] = {"status": "running", "done": 0, "total": 0, "items": [], "dir": jdir, "t0": time.time()}

    if mode == "logo":
        assets = {}
        pack_id = str(body.get("pack_id") or "")
        if pack_id and pack_id.isalnum():
            adir = os.path.join(DATA_DIR, pack_id, "assets")
            if os.path.isdir(adir):
                keymap = {"logo": "logo-navy.png", "logo_white": "logo-white.png",
                          "mark": "mark-navy.png", "mark_white": "mark-white.png",
                          "app_badge": "app-badge.png"}
                for k, fn in keymap.items():
                    p = os.path.join(adir, fn)
                    if os.path.exists(p):
                        assets[k] = p
        concept = str(body.get("concept") or "")
        if concept:
            m = re.match(r"^([0-9a-f]{32})/(concept_\d\.png)$", concept)
            if m:
                p = os.path.join(DATA_DIR, m.group(1), m.group(2))
                if os.path.exists(p):
                    assets = {"logo": p, "mark": p}
        if not assets:
            jobs.pop(jid, None)
            return jsonify(ok=False, error="No usable assets. Extract a logo or pick a concept first."), 400
        t = threading.Thread(target=_run_logo_job, args=(jid, assets, palette, name), daemon=True)
    elif mode == "scratch":
        desc = str(body.get("desc") or "a modern brand")[:200]
        style = str(body.get("style") or "modern")
        t = threading.Thread(target=_run_scratch_job, args=(jid, name, desc, style, palette), daemon=True)
    else:
        jobs.pop(jid, None)
        return jsonify(ok=False, error="mode must be 'logo' or 'scratch'."), 400

    if not _rate_ok(_client_ip()):
        jobs.pop(jid, None)
        return jsonify(ok=False, error="Rate limit reached, try again in an hour."), 429

    t.start()
    return jsonify(ok=True, job_id=jid)


@app.get("/api/job/<jid>")
def job_status(jid):
    j = jobs.get(jid)
    if not j and re.match(r"^[0-9a-f]{32}$", jid):
        # restart fallback: resurrect finished jobs from disk
        sp = os.path.join(DATA_DIR, jid, "status.json")
        if os.path.exists(sp):
            try:
                with open(sp) as f:
                    d = json.load(f)
                j = {"status": d.get("status", "done"), "done": d.get("done", 0),
                     "total": d.get("total", 0), "items": d.get("items", []),
                     "dir": os.path.join(DATA_DIR, jid), "t0": time.time(),
                     "full": d.get("full"), "deck": d.get("deck"),
                     "deck_error": d.get("deck_error")}
                with lock:
                    jobs.setdefault(jid, j)
            except (OSError, ValueError):
                pass
    if not j:
        abort(404)
    done = j["status"] == "done"
    return jsonify(ok=True, status=j["status"], done=j["done"], total=j["total"],
                   items=j["items"],
                   download="/api/pack/%s.zip" % jid if done else None,
                   preview="/api/preview/%s.pdf" % jid if done and j.get("deck") else None,
                   full=bool(j.get("full")), deck_error=j.get("deck_error"))


def _dl_token(jid):
    # never fall back to a guessable key: callers must check MOYASAR_SK first
    return hmac.new(MOYASAR_SK.encode(), ("full:" + jid).encode(),
                    hashlib.sha256).hexdigest()


@app.get("/api/preview/<jid>.pdf")
def preview_pdf(jid):
    if not re.match(r"^[0-9a-f]{32}$", jid):
        abort(404)
    p = os.path.join(DATA_DIR, jid, "preview.pdf")
    if not os.path.exists(p):
        abort(404)
    return send_file(p, mimetype="application/pdf", as_attachment=True,
                     download_name="brand-guideline-preview.pdf")


@app.get("/api/pay/verify")
def pay_verify():
    """Client returns from Moyasar with ?payment_id=..&job=.. — verify with the
    secret key server side, then mint the full-download token."""
    if not MOYASAR_SK:
        return jsonify(ok=False, error="Payments are not configured."), 503
    if not _rate_ok(_client_ip(), 20, "v:"):
        return jsonify(ok=False, error="Too many attempts, wait a minute."), 429
    pid = (request.args.get("payment_id") or "").strip()
    jid = (request.args.get("job") or "").strip()
    if not re.match(r"^[\w-]{8,64}$", pid) or not re.match(r"^[0-9a-f]{32}$", jid):
        return jsonify(ok=False, error="Bad request."), 400
    try:
        req = urllib.request.Request(
            "https://api.moyasar.com/v1/payments/" + pid,
            headers={"Authorization": "Basic " + base64.b64encode((MOYASAR_SK + ":").encode()).decode()})
        pay = json.load(urllib.request.urlopen(req, context=CTX, timeout=30))
    except Exception:
        return jsonify(ok=False, error="Could not verify the payment, try again."), 502
    meta = pay.get("metadata") or {}
    if pay.get("status") != "paid":
        return jsonify(ok=False, error="Payment not completed (status: %s)." % pay.get("status")), 402
    if pay.get("amount") != PRICE_HALALAS or pay.get("currency") != "SAR":
        return jsonify(ok=False, error="Payment amount mismatch."), 402
    if meta.get("job_id") != jid:
        return jsonify(ok=False, error="Payment does not match this document."), 402

    # Payment good. Launch (or reuse) the paid continuation: render the remaining
    # products and the full guideline. Idempotent per job.
    jdir = os.path.join(DATA_DIR, jid)
    if not os.path.isdir(jdir):
        return jsonify(ok=False, error="This job expired. Contact support with your payment reference for a refund."), 410
    with lock:
        j = jobs.get(jid)
        if j is None:
            # process restarted since the free run; rebuild the entry from disk
            j = {"status": "done", "done": 0, "total": 0, "items": [], "dir": jdir, "t0": time.time()}
            jobs[jid] = j
        start = not j.get("paid_started")
        j["paid_started"] = True
    if start:
        try:
            with open(os.path.join(jdir, "meta.json")) as f:
                m = json.load(f)
        except OSError:
            m = {"name": "the brand", "palette": []}
        assets = {}
        adir = os.path.join(jdir, "assets")
        if os.path.isdir(adir):
            keymap = {"logo": "logo-navy.png", "logo_white": "logo-white.png",
                      "mark": "mark-navy.png", "mark_white": "mark-white.png",
                      "app_badge": "app-badge.png"}
            for k, fn in keymap.items():
                p = os.path.join(adir, fn)
                if os.path.exists(p):
                    assets[k] = p
            for fn in sorted(os.listdir(adir)):
                if fn.startswith("concept_"):
                    assets.setdefault("logo", os.path.join(adir, fn))
                    assets.setdefault("mark", os.path.join(adir, fn))
        j.update(status="running", done=0, total=0, items=[
            {"name": k[:-4], "url": "/api/file/%s/%s" % (jid, k)}
            for k in sorted(os.listdir(jdir)) if k.endswith(".png")])
        threading.Thread(target=_run_logo_job,
                         args=(jid, assets, m.get("palette") or [], m.get("name") or "the brand", True),
                         daemon=True).start()
    return jsonify(ok=True, job_id=jid, url="/api/full/%s.pdf?t=%s" % (jid, _dl_token(jid)))


@app.get("/api/full/<jid>.pdf")
def full_pdf(jid):
    if not MOYASAR_SK:
        abort(503)  # paywall unconfigured must never mean free
    if not re.match(r"^[0-9a-f]{32}$", jid):
        abort(404)
    t = request.args.get("t", "")
    if not hmac.compare_digest(t, _dl_token(jid)):
        abort(403)
    p = os.path.join(DATA_DIR, jid, "full.pdf")
    if not os.path.exists(p):
        abort(404)
    return send_file(p, mimetype="application/pdf", as_attachment=True,
                     download_name="brand-guideline.pdf")


@app.get("/api/file/<jid>/<name>")
def job_file(jid, name):
    if not re.match(r"^[0-9a-f]{32}$", jid) or not re.match(r"^[\w-]+\.png$", name):
        abort(404)
    p = os.path.join(DATA_DIR, jid, name)
    if not os.path.exists(p):
        abort(404)
    return send_file(p, mimetype="image/png")


@app.get("/api/pack/<pid>.zip")
def pack(pid):
    if not pid.isalnum():
        abort(404)
    zpath = os.path.join(DATA_DIR, pid + ".zip")
    if not os.path.exists(zpath):
        abort(404)
    return send_file(zpath, mimetype="application/zip", as_attachment=True,
                     download_name="brand-kit.zip")


@app.errorhandler(413)
def too_big(e):
    return jsonify(ok=False, error="Logo too large. Keep it under 10 MB."), 413


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=int(os.environ.get("PORT", "3025")))
