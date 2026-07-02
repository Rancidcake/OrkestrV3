# ORKESTER

ORKESTER is a document assistant that processes text, PDFs, images, audio, and YouTube videos. Upload your files, ask questions, and receive answers with source citations.

## Features

- **Text** – Plain queries and conversational Q&A
- **PDF** – Native text and scanned documents (OCR)
- **Image** – OCR or visual description
- **Audio** – mp3, wav, m4a (Whisper transcription)
- **YouTube** – Automatic transcript fetching
- **Multi-input** – Cross-source comparison and QA

## How It Works

Content is extracted from each input, intent is classified, and the system picks the right approach: summarize, analyze sentiment, answer questions, compare, or explain code. It then runs the necessary tools, uses BM25 to retrieve the top matching chunks with their sources, and returns a plain text answer along with a trace of the agent’s reasoning and usage metrics.

## ARCHITECTURE
<img width="1090" height="1599" alt="PHOTO-2026-07-02-19-30-24" src="https://github.com/user-attachments/assets/8a9df281-9acc-4037-8b86-8f819066bad2" />


## Stack

- **Backend** – FastAPI
- **Agent** – LangGraph StateGraph
- **LLMs** – Groq llama-3.3-70b-versatile (primary), Groq llama3-8b-8192 and Gemini 2.5 Flash (fallbacks)
- **STT** – Groq whisper-large-v3
- **Vision** – Gemini 2.5 Flash, Mistral OCR, Tesseract
- **PDF** – pdfplumber and PyMuPDF for native text; pdf2image + OpenCV + Tesseract for scanned docs
- **RAG** – Pure Python BM25 (no vector DB)
- **YouTube** – youtube-transcript-api with Webshare proxy
- **Frontend** – Next.js 14
- **Deploy** – Render (Docker) for backend, Vercel for frontend

## Environment Variables

```
GROQ_API_KEY=
GEMINI_API_KEY=
MISTRAL_API_KEY=
WEBSHARE_PROXY_USER=   # Optional, for YouTube on cloud IPs
WEBSHARE_PROXY_PASS=   # Optional
```

## Run Locally

```bash
# Backend
cd /path/to/project
source .env
uvicorn backend.main:app --reload --port 8000

# Frontend (separate terminal)
cd frontend
npm run dev
```

The frontend proxies `/chat` and `/health` to the backend. Open http://localhost:3000.

## Deploy

**Backend**: Connect your repo to Render. It auto-detects `render.yaml` for Docker deployment on the free tier, with `/health` as the check endpoint. Add the three API keys as environment variables in the Render dashboard.

**Frontend**: Connect your repo to Vercel, set the root directory to `frontend`, and add `BACKEND_URL=https://your-render-url.onrender.com` as an environment variable.
