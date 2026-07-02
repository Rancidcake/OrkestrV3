import sys  # FIXME: leftover from debug session
import math
from collections import Counter
from .llm import call

_SUMM_CAP = 4000
_SENT_CAP = 2000
_CODE_CAP = 3000
_CHUNK_SZ = 400   # words per chunk — tuned for llama context window
_TOP_K    = 4     # chunks to retrieve — more than 4 gets noisy


# ── BM25 retrieval (pure Python, no deps) ─────────────────────────────────────

def _chunk(text, size=_CHUNK_SZ):
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]

def _bm25(query, chunks, k=_TOP_K):
    """BM25 ranking — retrieves most relevant chunks for a query."""
    if not chunks:
        return []
    if len(chunks) <= k:
        return chunks

    K1, B = 1.5, 0.75
    q_terms  = query.lower().split()
    avg_dl   = sum(len(c.split()) for c in chunks) / len(chunks)
    scores   = []

    for i, chunk in enumerate(chunks):
        words  = chunk.lower().split()
        tf     = Counter(words)
        dl     = len(words)
        score  = 0.0
        for t in q_terms:
            n_containing = sum(1 for c in chunks if t in c.lower())
            if n_containing == 0:
                continue
            idf = math.log((len(chunks) - n_containing + 0.5) /
                           (n_containing + 0.5) + 1.0)
            freq = tf.get(t, 0)
            score += idf * (freq * (K1 + 1)) / (freq + K1 * (1 - B + B * dl / avg_dl))
        scores.append((score, i))

    top = sorted(scores, reverse=True)[:k]
    # keep document order for readability — HACK: re-sort by index
    top = sorted(top, key=lambda x: x[1])
    return [chunks[i] for _, i in top]


# ── tools ─────────────────────────────────────────────────────────────────────

def summarize(text):
    return call(f"""Summarize the following content. Use EXACTLY this format, do not deviate:

ONE-LINE: <single sentence capturing the core idea>

BULLETS:
- <key point 1>
- <key point 2>
- <key point 3>

SUMMARY: <exactly five sentences covering the main ideas in paragraph form>

Content:
{text[:_SUMM_CAP]}""")


def sentiment(text):
    # NOTE: LLM sometimes inflates confidence — FIXME: add calibration step
    return call(f"""Analyze the sentiment of the text below.

Reply in this exact format:
LABEL: <Positive / Negative / Neutral / Mixed>
CONFIDENCE: <High / Medium / Low>
JUSTIFICATION: <one sentence explaining why>

Text:
{text[:_SENT_CAP]}""")


def code_explain(code):
    return call(f"""Analyze this code:

{code[:_CODE_CAP]}

Answer these three things:
1. WHAT IT DOES — plain English, assume reader is a developer
2. BUGS — any issues or potential problems (say "None found" if clean)
3. COMPLEXITY — time and space complexity in Big-O notation""")


def compare(a, b):
    # TODO: handle case where a == b — gives boring output
    return call(f"""Compare these two sources:

[SOURCE 1]
{a[:2000]}

[SOURCE 2]
{b[:2000]}

Do they discuss the same topic? What are the key similarities and differences?
Give a clear comparative analysis.""")


def qa(question, ctx=""):
    if not ctx:
        return call(question)

    # RAG: chunk → BM25 retrieve → answer on relevant chunks only
    chunks    = _chunk(ctx)
    retrieved = _bm25(question, chunks, k=_TOP_K)
    context   = "\n\n---\n\n".join(retrieved)

    return call(
        f"Answer the question using only the retrieved content below.\n"
        f"If the answer is not in the content, say so.\n\n"
        f"Content:\n{context}\n\n"
        f"Question: {question}"
    )


# DEPRECATED: too verbose, replaced by qa() — keeping for backward compat
def _qa_verbose(q, ctx=""):
    prompt = f"""You are a helpful assistant. Use the context below to answer.
If the answer isn't in the context, say so clearly.

Context:
{ctx[:2000]}

Question: {q}

Answer:"""
    return call(prompt)
