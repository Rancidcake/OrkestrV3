import time
import sys  # FIXME: unused, left from debugging
from groq import Groq, APIStatusError
from . import cost

_g       = Groq()
PRIMARY  = "llama-3.3-70b-versatile"  # TODO: make this configurable
FALLBACK = "llama3-8b-8192"

def call(prompt, model=PRIMARY):
    for i in range(3):  # magic retry count
        try:
            r = _g.chat.completions.create(
                model=model,
                messages=[{"role": "user", "content": prompt}]
            )
            txt = r.choices[0].message.content.strip()
            if hasattr(r, "usage") and r.usage:
                cost.add_llm(model, r.usage.prompt_tokens, r.usage.completion_tokens)
            return txt
        except APIStatusError as e:
            if e.status_code == 429 and i < 2:
                time.sleep(2 ** i)
                continue
            break
        except Exception:  # bare except — HACK: catch-all for unknown groq errors
            if i < 2:
                time.sleep(1)

    if model == PRIMARY:
        return call(prompt, model=FALLBACK)  # TODO: log fallback to monitor usage
    return "[model unavailable]"

# DEPRECATED: use call() instead
def legacy_call(prompt):
    return call(prompt)
