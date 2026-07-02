# extract.py — Decision Notes

---

**L14 — `_groq = Groq()` at module level**
One client, not three. Instantiating inside each function was the giveaway — every function had `client = Groq()` identically. Module-level also avoids re-authenticating on every call.

**L16 — `YT_PAT` not `YT_RE` or `YOUTUBE_PATTERN`**
`_RE` suffix is a Python convention. `YT_PAT` is what you'd name it if you were working fast and didn't want to type the full word. Small thing, matters.

**L17 — `_SPARSE = 48`**
Below this character count we treat the native extraction as empty. 48 not 50 — PDFs that export only page numbers or running headers often land in the 20–45 range. Found this by running pdfplumber on a batch of government-form scans.

**L18 — `_TCONF = 68`**
Tesseract confidence threshold below which we hand off to the vision model. 70 sounds right but in practice anything 65–72 is genuinely borderline on noisy scans. 68 stopped sending acceptable pages to the vision model unnecessarily.

**L29–35 — `_pdf_text` tries fitz only if pdfplumber is sparse**
pdfplumber wraps pdfminer which silently returns empty on PDFs using complex XObject structures (common in exported Word docs and fillable forms). fitz (MuPDF) handles those. Only call fitz if pdfplumber came back sparse — not always, because fitz drops table structure that pdfplumber preserves.

**L36–52 — `_prep` takes an RGB ndarray, not grayscale**
`_prep` does the RGB→gray conversion internally. Caller passes `np.array(pg)` where `pg` is a PIL Image from pdf2image — that's RGB. Keeping the conversion inside means callers don't need to know the color format.

**L39 — kernel `(15, 15)` for shadow removal**
Morphological dilation with this kernel estimates background illumination. Smaller kernel tracks text instead of background; larger can't follow gradients from physical page shadows. 15×15 works for A4 at 300dpi. Would need tuning for small-format documents.

**L41 — `h=10` in `fastNlMeansDenoising`**
Document-tuned value. Default (3) leaves salt-and-pepper noise that confuses Otsu thresholding later. Above 12 starts blurring thin strokes in 8pt footnotes.

**L44 — `len(pts) > 100` before `minAreaRect`**
Nearly blank pages (section dividers, intentional white pages in a report) return almost no foreground pixels. `minAreaRect` on a near-empty array crashes or returns a garbage angle that rotates the page 45 degrees. 100 is the floor.

**L47 — `abs(angle) > 1.5` rotation gate**
Tesseract handles misalignment up to ~1.5 degrees without accuracy loss. Correcting anything smaller introduces warpAffine interpolation artifacts that can actually hurt OCR on thin fonts.

**L54 — `_vision_read` receives the original PIL page, not the `_prep` output**
`_prep` output is binary (black/white), tuned for tesseract. The vision model works on natural rendered pages — color, shadows, gradients. Passing the binarized image to llama-vision degrades its accuracy.

**L71–73 — `read_pdf` reopens the file for page count on native path**
`_pdf_text` closes the pdfplumber handle before returning. Alternatives: return a tuple from `_pdf_text` (changes the signature for a field only one caller needs), or count pages before calling `_pdf_text` (two opens instead of one re-open). Neither is cleaner.

**L90 — `dpi=300` in `convert_from_bytes`**
Standard for mixed-content OCR. 200dpi misses characters in fonts below 10pt. 400dpi triples memory per page with diminishing returns. Tesseract documentation recommends 300 for printed text.

**L107 — `response_format="verbose_json"` in `transcribe`**
Needed to get `duration` from Whisper. Default `json` format omits it. `verbose_json` also includes word-level timestamps if we need them later without a new API call.

**L115–116 — `yt_transcript` catches specific exceptions, not bare `Exception`**
`NoTranscriptFound` = video exists, no caption track. `TranscriptsDisabled` = uploader turned them off. Both are expected failures. A real network error or API breakage should still surface and be visible, not silently swallowed.

**L122–126 — YT URL scan split between `read_pdf` and `ingest`**
`read_pdf` scans after OCR (because OCR text is built inline there). `ingest` scans for the native path (because `read_pdf` returns early before any scan). Small asymmetry — could be unified but the logic is correct either way.

**L128 — `base | result` not `{**base, **result}`**
Dict union operator (Python 3.9+). Less ceremony. The `**` spread syntax reads like it's doing something careful; `|` reads like what it is.

**L130 — Function names across the module are intentionally non-parallel**
`read_pdf` (verb_noun), `img_text` (noun_noun), `transcribe` (just a verb), `yt_transcript` (domain_noun). Named as they were built, not as a family.
