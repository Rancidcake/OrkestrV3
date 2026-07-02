# DSAI Assignment — Build Plan

**Stack:** Groq · LangGraph · FastAPI · Next.js (v0) · Render + Vercel  
**Deadline:** 48h

---

## Architecture

```
[Next.js Chat UI]  ←  deployed on Vercel
        ↕  HTTP + CORS  (NEXT_PUBLIC_API_URL)
[FastAPI + LangGraph]  ←  deployed on Render (Docker)
```

Frontend and backend are fully decoupled.  
Vercel hosts the UI. Render hosts the API (no serverless timeout issues for audio/PDF).

---

## Repo Structure

```
/
├── backend/
│   ├── main.py          # FastAPI app — /chat, /health, CORS
│   ├── graph.py         # LangGraph StateGraph (the brain)
│   ├── extract.py       # pdf / image / audio / youtube → {text, status, confidence}
│   ├── tools.py         # summarize, sentiment, code_explain, compare
│   ├── llm.py           # Groq client + retry + model fallback
│   ├── Dockerfile
│   ├── render.yaml
│   └── requirements.txt
│
├── frontend/            # generated via v0.dev, then wired up
│   ├── app/
│   │   └── page.tsx     # chat UI — file upload, chat bubbles, plan trace
│   ├── .env.example
│   └── vercel.json
│
├── tests/
│   ├── test_extract.py
│   ├── test_tools.py
│   └── test_graph.py
│
└── README.md
```

---

## LangGraph Flow

```
START
  │
  ▼
[extract]          — runs all uploaded files through extract.py in parallel
  │                  each input returns {text, status, confidence}
  │                  one input failing does NOT abort the request
  ▼
[plan]             — single Groq LLM call
  │                  input: unified extracted context + user query
  │                  output: either a clarifying question OR a tool chain list
  │
  ├─ ambiguous? ──► [clarify]  — return question to user, wait for reply
  │
  └─ clear? ──────► [execute]  — run each tool in the plan chain sequentially
                        │         appends to plan_trace after each step
                        ▼
                    [synthesize] — LLM formats final text-only answer
                        │
                       END
```

State shape:
```python
{
  "inputs":         [...],   # raw uploaded files + text
  "extracted":      [...],   # {source, text, status, confidence}
  "plan_trace":     [...],   # [{tool, input_summary, output_summary}]
  "clarifying_q":   str,     # set if plan decided to ask
  "answer":         str      # final text response
}
```

---

## Files — what each one does

### `llm.py`
- One Groq client instance.
- `call(prompt, model)` with 3 retries.
- On all retries exhausted → downgrade from `llama-3.3-70b` to `llama3-8b-8192`.
- If that also fails → return a plain error string (never raise to the user).

### `extract.py`
Five extractors, each independent:

| Input | Primary | Fallback 1 | Fallback 2 |
|-------|---------|------------|------------|
| PDF | native text (see pipeline below) | DIP → OCR (if permitted) | user message if not permitted |
| Image | Groq vision (llama-3.2-11b-vision) | tesseract local | — |
| Audio (mp3/wav/m4a) | Groq Whisper | error message + file metadata | — |
| YouTube URL | youtube-transcript-api | yt-dlp | "transcript unavailable" |
| Plain text | passthrough | — | — |

### PDF extraction pipeline

```
Try native text extraction
  │  (pdfplumber first, PyMuPDF if pdfplumber returns < 50 chars)
  │
  ├── text found → return {text, status: "native", confidence: 0.95}
  │
  └── no text (scanned / image-only)
        │
        ├── ocr_permitted = True (default)?
        │      │
        │      └── DIP (Document Image Processing)
        │               pdf2image → per-page images
        │               preprocess: deskew · denoise · binarize (Pillow/OpenCV)
        │               │
        │               └── tesseract OCR
        │                      │
        │                      └── return {text, status: "ocr", confidence: tesseract score}
        │
        └── ocr_permitted = False
               └── return {
                     text: null,
                     status: "ocr_not_permitted",
                     confidence: 0.0,
                     message: "This PDF has no extractable text layer. OCR is required
                               but not permitted for this file. Please provide an
                               accessible copy or authorize OCR processing."
                   }
```

`ocr_permitted` defaults to `True`. Frontend can expose a toggle if needed.

Every extractor returns:
```python
{"source": "file.pdf", "text": "...", "status": "ok|ocr_fallback|failed", "confidence": 0.0–1.0}
```

### `tools.py`
| Tool | Output |
|------|--------|
| `summarize(text)` | one-line · three bullets · five sentences |
| `sentiment(text)` | label · confidence · one-line justification |
| `code_explain(text)` | what it does · bugs · time complexity |
| `compare(texts[])` | unified comparative analysis |

All tools call `llm.py`. None do their own parsing.

### `graph.py`
- `StateGraph` with nodes: `extract`, `plan`, `clarify`, `execute`, `synthesize`.
- Conditional edge after `plan`: ambiguous → `clarify`, clear → `execute`.
- `execute` iterates the tool chain, appends each step to `plan_trace`.
- `synthesize` formats `plan_trace` + tool outputs into final answer.

### `main.py`
```
POST /chat
  body: {text: str, files: [base64+mime]}
  returns: {extracted, plan_trace, clarifying_q, answer}

GET /health
```
CORS open for the Vercel frontend domain.

---

## Fallbacks (Robustness — 15 marks)

Every failure is contained. The request always returns something useful.

```
PDF parse fails       → try OCR, if OCR fails → extracted.status = "failed", skip this input
Image OCR fails       → tesseract, if tesseract missing → "could not extract image text"
Audio STT fails       → "audio received but transcription unavailable: <filename>"
YouTube unavailable   → "transcript not available for this video"
LLM call fails        → retry 3x → downgrade model → return graceful error string
All inputs fail       → return clarifying_q asking user to re-upload
```

---

## Frontend (v0 prompt → Next.js)

I'll write a v0.dev prompt that generates:
- Chat bubble layout (user messages on right, agent on left)
- Multi-file upload (PDF, image, audio — multiple at once)
- `Extracted content` collapsible section (shows per-file status + confidence)
- `Plan trace` accordion (shows which tools ran, in order)
- Text-only response area
- Loading state while agent runs

One env var: `NEXT_PUBLIC_API_URL=https://your-render-app.onrender.com`

---

## Deployment

### Backend → Render
- Docker build from `backend/Dockerfile`
- `render.yaml` sets env vars: `GROQ_API_KEY`
- Free tier: 512MB RAM, no cold-start timeout on HTTP (unlike Vercel serverless)

### Frontend → Vercel
- `git push` → Vercel auto-deploys Next.js
- Set `NEXT_PUBLIC_API_URL` in Vercel dashboard → points to Render backend

---

## Evaluation mapping

| Criterion | Marks | How we hit it |
|-----------|------:|---------------|
| Correctness | 30 | All 5 test cases covered in extract + tools |
| Autonomy & Planning | 20 | LangGraph planner builds minimal tool chain automatically |
| Robustness | 15 | Every extractor has a fallback, LLM has retry + downgrade |
| Explainability | 10 | `plan_trace` returned in every response, shown in UI |
| Code Quality | 10 | Flat structure, minimal deps, Docker, tests |
| UX & Demo | 10 | v0 chat UI, file upload, trace accordion |

**Target: 95+**

---

## Build order

- [ ] `llm.py` — Groq client + retry
- [ ] `extract.py` — all five extractors + fallbacks
- [ ] `tools.py` — summarize, sentiment, code_explain, compare
- [ ] `graph.py` — LangGraph StateGraph
- [ ] `main.py` — FastAPI wrapper
- [ ] `Dockerfile` + `render.yaml`
- [ ] v0 prompt → wire frontend
- [ ] `vercel.json` + `.env.example`
- [ ] `tests/`
- [ ] `README.md`

---

## Env vars needed

```env
GROQ_API_KEY=          # backend (Render)
NEXT_PUBLIC_API_URL=   # frontend (Vercel) — points to Render URL
```

Tesseract installed via Dockerfile (`apt-get install tesseract-ocr`). No extra key needed.
