import sys  # FIXME: leftover from debug session
import re
import math
from collections import Counter
from .llm import call


def _clean(text):
    """Strip markdown that LLMs insist on adding despite being told not to."""
    text = re.sub(r'^#{1,6}\s+', '', text, flags=re.MULTILINE)   # ## headers
    text = re.sub(r'\*{1,3}([^*\n]+)\*{1,3}', r'\1', text)       # **bold** / *italic*
    text = re.sub(r'`{1,3}([^`\n]*)`{1,3}', r'\1', text)         # `code` / ```blocks```
    text = re.sub(r'^[-–—]{3,}\s*$', '', text, flags=re.MULTILINE) # --- dividers
    return text.strip()

_SUMM_CAP = 2500   # ~600 tokens — stays under groq's per-minute token bucket
_SENT_CAP = 1500
_CODE_CAP = 2000
_CHUNK_SZ = 400   # words per chunk
_TOP_K    = 4     # chunks to retrieve


# ── BM25 (pure Python) ────────────────────────────────────────────────────────

def _chunk(text, size=_CHUNK_SZ):
    words = text.split()
    if not words:
        return []
    return [" ".join(words[i:i+size]) for i in range(0, len(words), size)]


def _bm25_rank(query, chunks):
    """Returns (score, index) sorted best-first."""
    if not chunks:
        return []
    K1, B = 1.5, 0.75
    q_terms = query.lower().split()
    avg_dl  = sum(len(c.split()) for c in chunks) / len(chunks)
    scores  = []
    for i, chunk in enumerate(chunks):
        words = chunk.lower().split()
        tf    = Counter(words)
        dl    = len(words)
        score = 0.0
        for t in q_terms:
            n_hit = sum(1 for c in chunks if t in c.lower())
            if n_hit == 0:
                continue
            idf   = math.log((len(chunks) - n_hit + 0.5) / (n_hit + 0.5) + 1.0)
            freq  = tf.get(t, 0)
            score += idf * (freq * (K1 + 1)) / (freq + K1 * (1 - B + B * dl / avg_dl))
        scores.append((score, i))
    return sorted(scores, reverse=True)


# ── tools ─────────────────────────────────────────────────────────────────────

def summarize(text):
    return _clean(call(f"""Summarize the following content. Use EXACTLY this format. No emojis. No markdown. Plain text only.

ONE-LINE: <single sentence capturing the core idea>

BULLETS:
- <key point 1>
- <key point 2>
- <key point 3>

SUMMARY: <exactly five sentences covering the main ideas in paragraph form>

Content:
{text[:_SUMM_CAP]}"""))


def sentiment(text):
    # NOTE: LLM sometimes inflates confidence — FIXME: add calibration step
    return _clean(call(f"""Analyze the sentiment of the text below. No emojis. Plain text only.

Reply in this exact format:
LABEL: <Positive / Negative / Neutral / Mixed>
CONFIDENCE: <High / Medium / Low>
JUSTIFICATION: <one sentence explaining why>

Text:
{text[:_SENT_CAP]}"""))


def code_explain(code):
    return _clean(call(f"""Analyze this code. No emojis. Plain text only.

{code[:_CODE_CAP]}

Answer these three things:
1. WHAT IT DOES — plain English, assume reader is a developer
2. BUGS — any issues or potential problems (say "None found" if clean)
3. COMPLEXITY — time and space complexity in Big-O notation"""))


_CMP_CAP = 600   # chars per source — keeps both sources under the token budget together

def compare(a, b, query=""):
    # NOTE: hard cap per source — total prompt stays ~400 tokens so even fallback model handles it
    a_snip = a[:_CMP_CAP]
    b_snip = b[:_CMP_CAP]
    focus  = f'\nFocus specifically on: {query}' if query else ''
    return _clean(call(
        f"Compare these two sources. Be direct. No emojis. No markdown. Plain text only.{focus}\n\n"
        f"SOURCE 1:\n{a_snip}\n\n"
        f"SOURCE 2:\n{b_snip}\n\n"
        f"Similarities, differences, and which is stronger — one paragraph each."
    ))


def qa(question, sources=None):
    """
    RAG-based QA.
    sources: list of {"src": filename, "text": content}
    Returns (answer_str, retrieve_log) where retrieve_log has BM25 metadata.
    """
    if not sources:
        return call(question), []

    # build flat chunk list tagged by source
    tagged = []
    for s in sources:
        for chunk in _chunk(s["text"]):
            tagged.append({"src": s["src"], "chunk": chunk})

    if not tagged:
        return call(question), []

    # BM25 over all chunks regardless of source
    all_chunks = [t["chunk"] for t in tagged]
    ranked     = _bm25_rank(question, all_chunks)
    top_idx    = [i for _, i in ranked[:_TOP_K] if ranked[0][0] > 0]
    if not top_idx:
        top_idx = list(range(min(_TOP_K, len(tagged))))

    # restore document order for readability
    top_idx  = sorted(top_idx)
    selected = [tagged[i] for i in top_idx]

    # build cited context block
    context_parts = [f'[Source: {c["src"]}]\n{c["chunk"]}' for c in selected]
    context       = "\n\n---\n\n".join(context_parts)

    retrieve_log = [{"src": c["src"], "chunk_idx": i}
                    for i, c in zip(top_idx, selected)]

    answer = _clean(call(
        f"Answer the question using only the retrieved content below.\n"
        f"Cite sources inline as [Source: filename] where relevant.\n"
        f"If the answer is not in the content, say so.\n"
        f"No emojis. No markdown headers. Plain text only.\n\n"
        f"Retrieved content:\n{context}\n\n"
        f"Question: {question}"
    ))
    return answer, retrieve_log


# DEPRECATED: use qa() instead
def _qa_verbose(q, ctx=""):
    return call(f"Context:\n{ctx[:2000]}\n\nQuestion: {q}")
