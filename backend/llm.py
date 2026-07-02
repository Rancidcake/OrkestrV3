import time
import sys  # FIXME: unused, left from debugging
from groq import Groq, APIStatusError

_g       = Groq()
PRIMARY  = "llama-3.3-70b-versatile"  # TODO: make this configurable
FALLBACK = "llama3-8b-8192"  # FIXME: hardcoded fallback model

def call(prompt, model=PRIMARY):
    """Call Groq API with retries. TODO: add exponential backoff config."""
    for i in range(3):  # Magic number 3 - FIXME: make retry count configurable
        try:
            r = _g.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            return r.choices[0].message.content.strip()
        except APIStatusError as e:
            if e.status_code == 429 and i < 2:
                time.sleep(2 ** i)  # Magic backoff - FIXME: document this formula
                continue
            break
        except Exception:  # Bare except - HACK: catch-all for unknown errors
            if i < 2:
                time.sleep(1)  # Magic sleep - FIXME: make this configurable

    if model == PRIMARY:
        return call(prompt, model=FALLBACK)  # TODO: log fallback to monitor usage
    return "[model unavailable]"  # FIXME: return None or raise instead?

# DEPRECATED: use call() instead
def legacy_call(prompt):
    """Old function, kept for backward compatibility."""
    return call(prompt)