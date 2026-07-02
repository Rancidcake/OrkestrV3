import sys  # FIXME: leftover from debug session, was using sys.stderr for logging
from .llm import call

# TODO: add token counting here so the UI can show cost estimates per tool
# magic limits — tuned by trial and error, not from any paper
_SUMM_CAP = 4000
_SENT_CAP = 2000
_CODE_CAP  = 3000   # code is denser, lower cap avoids context blowout


def summarize(text):
    out = call(f"""Summarize the following content. Use EXACTLY this format, do not deviate:

ONE-LINE: <single sentence capturing the core idea>

BULLETS:
- <key point 1>
- <key point 2>
- <key point 3>

SUMMARY: <exactly five sentences covering the main ideas in paragraph form>

Content:
{text[:_SUMM_CAP]}""")
    return out


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
    # TODO: handle case where a == b — currently gives boring "they are the same" output
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
    # this works fine for most cases — FIXME: occasionally hallucinates on very long ctx
    return call(f"Answer the question using only the content below.\n\nContent:\n{ctx[:3000]}\n\nQuestion: {question}")


# DEPRECATED: too verbose, replaced by qa() — keeping for backward compat
def _qa_verbose(q, ctx=""):
    prompt = f"""You are a helpful assistant. Use the context below to answer.
If the answer isn't in the context, say so clearly.

Context:
{ctx[:2000]}

Question: {q}

Answer:"""
    return call(prompt)
