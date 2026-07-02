import os
import time
import sys  # FIXME: unused, left from debugging
from groq import Groq, APIStatusError
from google import genai
from . import cost

_g   = Groq()
_gem = genai.Client(api_key=os.environ.get("GEMINI_API_KEY", ""))

PRIMARY  = "llama-3.3-70b-versatile"
FALLBACK = "llama3-8b-8192"
_SYS     = ("You are a helpful assistant. "
             "Never use emojis. "
             "Never use markdown like **, ##, or ---. "
             "Write in plain text only.")

_MAX_CHARS = {
    PRIMARY:  12000,   # ~3k tokens, safe under 12k/min token limit
    FALLBACK:  4000,   # 8192 token ctx window — be conservative
}


def _try_groq(prompt, model, retries=3):
    cap = _MAX_CHARS.get(model, 4000)
    if len(prompt) > cap:
        prompt = prompt[:cap] + "\n[truncated]"

    for i in range(retries):
        try:
            r = _g.chat.completions.create(
                model=model,
                messages=[
                    {"role": "system", "content": _SYS},
                    {"role": "user",   "content": prompt},
                ]
            )
            txt = r.choices[0].message.content.strip()
            if hasattr(r, "usage") and r.usage:
                cost.add_llm(model, r.usage.prompt_tokens, r.usage.completion_tokens)
            return txt

        except APIStatusError as e:
            if e.status_code == 429:
                # respect retry-after; if > 10s bail out — not worth waiting
                retry_after = int(e.response.headers.get("retry-after", "0"))
                if retry_after > 10:
                    return None
                time.sleep(min(2 ** i, 8))
                continue
            if e.status_code == 400:
                return None   # context window exceeded — nothing we can do
            if e.status_code >= 500:
                time.sleep(2)
                continue
            return None   # any other 4xx — don't retry

        except Exception:
            if i < retries - 1:
                time.sleep(1)

    return None


def _try_gemini(prompt):
    try:
        # Gemini 2.5 Flash — 1M token context, separate rate limits from Groq
        r = _gem.models.generate_content(
            model="gemini-2.5-flash",
            contents=f"{_SYS}\n\n{prompt}",
        )
        txt = r.text.strip() if r.text else None
        if txt:
            cost.add_llm("gemini-2.5-flash", 0, 0)   # usage not in basic response
        return txt
    except Exception:
        return None


def call(prompt, model=PRIMARY):
    # 1. try primary Groq model
    result = _try_groq(prompt, model)
    if result:
        return result

    # 2. try fallback Groq model (only if primary was actually tried)
    if model == PRIMARY:
        result = _try_groq(prompt, FALLBACK)
        if result:
            return result

    # 3. Gemini as final fallback — separate rate limits, huge context window
    result = _try_gemini(prompt)
    if result:
        return result

    return "Could not get a response — all models are rate limited right now. Wait a minute and try again."


# DEPRECATED: use call() instead
def legacy_call(prompt):
    return call(prompt)
