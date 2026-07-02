# ORKESTER - V 0.1
Dropping in Files and getting a answer.

## What goes In
1. Text - Query
2. PDF - .pdf (requires OCR , DIP and Native searchable )
3. Image - .jpg and .png
4. Audio - .mp3, .wav and .m4a (Maybe Whisper?)

## What comes out
TEXT , prefeably with document level citations, trace-log of each tool invoked and actual answer to the user query

## Stack
Backend - FastAPI
Agent - LangGraph
LLM - groq (llama-3.3-70b)
STT -  whisper-large-v3
Vision - llama-3.2-11b-vision
PDF (Native Text) - pdfplumber -> PyMuPDF
PDF (DIP) - pdf2image + OpenCV
PDF (OCR) - tesseract (post-DIP only)
YT Transcripts - youtube-transcripts-api
Frontend - Next.js

## Env Variables
GROQ_API_KEY=# Orkestr
