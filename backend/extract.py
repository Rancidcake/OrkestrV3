import io, re, base64, os
import logging
from . import cost

import cv2
import numpy as np
import pikepdf
import pdfplumber
import fitz
import pytesseract
from google import genai
from google.genai.types import Part
from mistralai import Mistral
from pdf2image import convert_from_bytes
from PIL import Image
from groq import Groq
from youtube_transcript_api import YouTubeTranscriptApi
from youtube_transcript_api.proxies import WebshareProxyConfig, GenericProxyConfig

log = logging.getLogger("orkester.extract")
logging.basicConfig(level=logging.DEBUG, format="%(levelname)s [%(name)s] %(message)s")

_groq    = Groq()
_gem     = genai.Client(api_key=os.environ["GEMINI_API_KEY"])
_mistral = Mistral(api_key=os.environ["MISTRAL_API_KEY"])

# YouTube blocks cloud IPs — use proxy if configured
_ws_user = os.environ.get("WEBSHARE_PROXY_USER")
_ws_pass = os.environ.get("WEBSHARE_PROXY_PASS")
if _ws_user and _ws_pass:
    _yt = YouTubeTranscriptApi(proxies=WebshareProxyConfig(
        proxy_username=_ws_user,
        proxy_password=_ws_pass,
    ))
    log.info("YouTube transcript using Webshare proxy")
else:
    _yt = YouTubeTranscriptApi()
    log.warning("No proxy set — YouTube may block transcript requests on cloud IPs")

YT_PAT   = re.compile(r"https?://(?:www\.)?(?:youtube\.com/watch\?v=|youtu\.be/)([A-Za-z0-9_-]{11})")
_TCONF   = 68

# SCC Online / Taxmann stamp the full copyright block on every page.
# After stripping, a real judgment has hundreds of chars; leftover boilerplate is ~80.
_WATERMARK = re.compile(
    r"SCC Online Web Edition[^\n]*\n?|"
    r"©[^\n]*(EBC|Eastern Book)[^\n]*\n?|"
    r"For private use only[^\n]*\n?|"
    r"Printed For[^\n]*\n?|"
    r"This text is protected[^\n]*\n?|"
    r"pursuant to the judgment[^\n]*\n?|"
    r"Eastern Book Company v\. D\.B\. Modak[^\n]*\n?|"
    r"TruePrint[^\n]*\n?|"
    r"-{10,}\n?|"
    r"Page \d+\s+(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday)[^\n]*\n?",
    re.IGNORECASE
)
_MIN_REAL = 300


def _clean(text):
    text = _WATERMARK.sub("", text)
    return re.sub(r"\n{3,}", "\n\n", text).strip()


def _unlock(blob):
    try:
        with pikepdf.open(io.BytesIO(blob)) as pdf:
            buf = io.BytesIO()
            pdf.save(buf)
            unlocked = buf.getvalue()
            log.info("pikepdf unlock OK (%d → %d bytes)", len(blob), len(unlocked))
            return unlocked
    except Exception as e:
        log.debug("pikepdf unlock skipped: %s", e)
        return blob


def _pdf_text(blob):
    blob = _unlock(blob)
    with pdfplumber.open(io.BytesIO(blob)) as f:
        raw  = [pg.extract_text() for pg in f.pages]
        n    = len(raw)
        raw_joined = "\n\n".join(r or "" for r in raw)
        body = _clean(raw_joined)

    log.debug("pdfplumber raw chars: %d  |  after strip: %d  |  pages: %d",
              len(raw_joined), len(body), n)
    log.debug("pdfplumber sample (first 300): %r", body[:300])

    if len(body) >= _MIN_REAL:
        log.info("native text OK via pdfplumber (%d chars)", len(body))
        return body, n

    log.debug("pdfplumber below threshold — trying fitz")
    doc      = fitz.open(stream=blob, filetype="pdf")
    fitz_raw = "\n\n".join(p.get_text() for p in doc)
    body     = _clean(fitz_raw)
    n        = len(doc)
    doc.close()

    log.debug("fitz raw chars: %d  |  after strip: %d", len(fitz_raw), len(body))
    log.debug("fitz sample (first 300): %r", body[:300])

    if len(body) >= _MIN_REAL:
        log.info("native text OK via fitz (%d chars)", len(body))
        return body, n

    log.info("native text failed both — will OCR (body was %d chars after strip)", len(body))
    return "", n


def _prep(page_arr):
    gray = cv2.cvtColor(page_arr, cv2.COLOR_RGB2GRAY)

    bg   = cv2.dilate(gray, np.ones((15, 15), np.uint8))
    gray = cv2.divide(gray, bg, scale=255)
    # tried bilateral filter here — slower, didn't help on b&w scans
    gray = cv2.fastNlMeansDenoising(gray, h=10)

    _, inv = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    pts    = np.column_stack(np.where(inv > 0))

    if len(pts) > 100:
        angle = cv2.minAreaRect(pts)[-1]
        if angle < -45: angle += 90
        if abs(angle) > 1.5:
            h, w = gray.shape
            M    = cv2.getRotationMatrix2D((w//2, h//2), angle, 1.0)
            gray = cv2.warpAffine(gray, M, (w, h), flags=cv2.INTER_CUBIC,
                                  borderMode=cv2.BORDER_REPLICATE)

    clahe  = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))
    gray   = clahe.apply(gray)
    _, out = cv2.threshold(gray, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)

    black_ratio = np.sum(out == 0) / out.size
    log.debug("Otsu black ratio: %.2f", black_ratio)

    if black_ratio > 0.55:
        log.debug("switching to adaptive threshold (watermark detected)")
        out = cv2.adaptiveThreshold(gray, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
                                    cv2.THRESH_BINARY, 31, 12)
    return out


def _mistral_ocr(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    b64 = base64.b64encode(buf.getvalue()).decode()
    r   = _mistral.ocr.process(
        model="mistral-ocr-latest",
        document={"type": "image_url", "image_url": f"data:image/png;base64,{b64}"}
    )
    return "\n".join(p.markdown for p in r.pages).strip()


def _vision_read(img):
    try:
        buf = io.BytesIO()
        img.save(buf, format="PNG")
        r = _gem.models.generate_content(
            model="gemini-2.5-flash",
            contents=[Part.from_bytes(data=buf.getvalue(), mime_type="image/png"),
                      "Extract all text from this image exactly as it appears. Return only the text."]
        )
        cost.add_vision(1)
        return r.text.strip()
    except Exception as e:
        log.warning("Gemini blocked (%s) — Mistral OCR fallback", type(e).__name__)
    try:
        txt = _mistral_ocr(img)
        cost.add_vision(1)
        return txt
    except Exception as e2:
        log.warning("Mistral OCR failed (%s) — tesseract fallback", e2)
        clean = _prep(np.array(img))
        return pytesseract.image_to_string(clean).strip()


def read_pdf(blob, ocr=True, force_vision=False):
    if not force_vision:
        body, n = _pdf_text(blob)
        if body:
            return {"text": body, "how": "native", "pages": n,
                    "debug": f"native text extracted ({len(body)} chars)"}
    else:
        log.info("force_vision=True — skipping native text extraction")
        with pdfplumber.open(io.BytesIO(blob)) as f:
            n = len(f.pages)

    if not ocr:
        return {
            "text": None,
            "how":  "blocked",
            "err":  "no text layer — OCR not authorized, send an accessible copy"
        }

    rendered = convert_from_bytes(blob, dpi=300)
    out      = []
    page_log = []

    _GEM_PAGE_CAP = 3
    if force_vision:
        log.info("force_vision=True — Gemini on first %d pages, tesseract rest", _GEM_PAGE_CAP)
        for i, pg in enumerate(rendered):
            if i < _GEM_PAGE_CAP:
                txt = _vision_read(pg)
                tag = "vision(forced)"
            else:
                clean = _prep(np.array(pg))
                txt   = pytesseract.image_to_string(clean).strip()
                tag   = "tess(rest)"
            out.append(txt)
            page_log.append(f"p{i+1}:{tag}")
            log.debug("page %d [%s] — %d chars", i + 1, tag, len(txt))
    else:
        log.info("starting OCR on %d pages at 300dpi", len(rendered))
        all_confs = []
        for i, pg in enumerate(rendered):
            clean = _prep(np.array(pg))
            d     = pytesseract.image_to_data(clean, output_type=pytesseract.Output.DICT)
            confs = [c for c in d["conf"] if c != -1]
            avg   = sum(confs)/len(confs) if confs else 0
            all_confs.extend(confs)

            log.debug("page %d — tesseract avg conf: %.1f", i + 1, avg)

            if avg >= _TCONF:
                txt = pytesseract.image_to_string(clean)
                out.append(txt)
                page_log.append(f"p{i+1}:tess(conf={avg:.0f})")
                log.debug("page %d — tesseract OK, chars: %d", i + 1, len(txt))
            else:
                log.debug("page %d — conf too low (%.1f), calling vision model", i + 1, avg)
                txt = _vision_read(pg)
                out.append(txt)
                page_log.append(f"p{i+1}:vision")
                log.debug("page %d — vision returned %d chars", i + 1, len(txt))

    text   = "\n\n".join(out).strip()
    avg_conf = round(sum(all_confs) / len(all_confs), 1) if all_confs else None
    result = {
        "text":       text,
        "how":        "ocr",
        "pages":      len(rendered),
        "confidence": avg_conf,
        "debug":      " | ".join(page_log)
    }
    hits = YT_PAT.findall(text)
    if hits:
        result["yt_urls"] = ["https://youtu.be/" + v for v in hits]
    return result


def img_text(blob):
    img = Image.open(io.BytesIO(blob))
    try:
        r    = _gem.models.generate_content(
            model="gemini-2.5-flash",
            contents=[Part.from_bytes(data=blob, mime_type="image/png"),
                      "Describe what is in this image. Include any visible text verbatim."]
        )
        body = r.text.strip()
        if body:
            return {"text": body, "method": "vision"}
    except Exception as e:
        log.warning("Gemini img_text blocked (%s) — Mistral OCR fallback", type(e).__name__)

    try:
        body = _mistral_ocr(img)
        if body:
            return {"text": body, "method": "mistral-ocr"}
    except Exception as e2:
        log.warning("Mistral OCR img failed (%s) — tesseract fallback", e2)

    arr  = np.frombuffer(blob, np.uint8)
    gray = cv2.imdecode(arr, cv2.IMREAD_GRAYSCALE)
    body = pytesseract.image_to_string(gray).strip()
    return {"text": body or None, "method": "tess" if body else "failed"}


def transcribe(blob, fname):
    tx = _groq.audio.transcriptions.create(
        file=(fname, blob),
        model="whisper-large-v3",
        response_format="verbose_json"
    )
    cost.add_audio(tx.duration)
    return {"text": tx.text, "secs": tx.duration}


def yt_transcript(url):
    m = YT_PAT.search(url)
    if not m:
        return {"text": None, "vid": None, "err": "no video ID found in URL"}

    vid = m.group(1)
    try:
        tx   = _yt.fetch(vid)
        text = " ".join(s.text for s in tx).strip()
        if not text:
            return {"text": None, "vid": vid, "err": "transcript is empty — video may have no captions"}
        return {"text": text, "vid": vid}
    except Exception as e:
        err = str(e)
        # surface a friendly message for the two most common failures
        if "blocked" in err.lower() or "ipblocked" in err.lower():
            err = "YouTube blocked this IP (cloud server). Add WEBSHARE_PROXY_USER/PASS env vars to fix."
        elif "NoTranscriptFound" in err or "TranscriptsDisabled" in err:
            err = "No transcript available for this video (captions disabled or not generated)."
        return {"text": None, "vid": vid, "err": err}


def ingest(src, blob=None, mime="", ocr=True, force_vision=False):
    base = {"src": src}

    if mime == "application/pdf" or src.endswith(".pdf"):
        log.info("ingesting PDF: %s  force_vision=%s", src, force_vision)
        result = read_pdf(blob, ocr, force_vision)
        if result.get("text") and "yt_urls" not in result:
            hits = YT_PAT.findall(result["text"])
            if hits:
                result["yt_urls"] = ["https://youtu.be/" + v for v in hits]
        return {**base, **result}

    if mime.startswith("image/") or src.endswith((".jpg", ".jpeg", ".png")):
        return base | img_text(blob)

    if mime.startswith("audio/") or src.endswith((".mp3", ".wav", ".m4a")):
        return base | transcribe(blob, src)

    if YT_PAT.search(src):
        return base | yt_transcript(src)

    return base | {"text": src}
