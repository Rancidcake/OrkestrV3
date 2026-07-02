import threading

# ── pricing (approximate, mid-2025) ──────────────────────────────────────────
_PRICE = {
    "llama-3.3-70b-versatile": (0.59, 0.79),   # $/M tokens in/out
    "llama3-8b-8192":          (0.05, 0.08),
    "gemini-2.5-flash":        (0.075, 0.30),
    "whisper-large-v3":        0.111 / 3600,    # $/second of audio
    "mistral-ocr-latest":      1.00  / 1000,    # $/page
}

# carbon intensity — gCO2e estimates (rough, based on cloud GPU power + US grid)
# these are order-of-magnitude, not precise — FIXME: find a better source
_CO2_PER_1K_TOKENS = 0.002   # gCO2e per 1000 tokens
_CO2_PER_AUDIO_SEC = 0.0007  # gCO2e per second of whisper
_CO2_PER_VISION    = 0.30    # gCO2e per vision call (image/page)

_local = threading.local()


def reset():
    _local.calls = []


def _calls():
    if not hasattr(_local, "calls"):
        _local.calls = []
    return _local.calls


def add_llm(model, in_tokens, out_tokens):
    prices = _PRICE.get(model, (0.59, 0.79))
    usd    = (in_tokens * prices[0] + out_tokens * prices[1]) / 1_000_000
    co2    = (in_tokens + out_tokens) / 1000 * _CO2_PER_1K_TOKENS
    _calls().append({"type": "llm", "model": model,
                     "tokens": in_tokens + out_tokens, "usd": usd, "co2_g": co2})


def add_audio(secs):
    usd = secs * _PRICE["whisper-large-v3"]
    co2 = secs * _CO2_PER_AUDIO_SEC
    _calls().append({"type": "audio", "model": "whisper-large-v3",
                     "secs": secs, "usd": usd, "co2_g": co2})


def add_vision(n_pages=1):
    # gemini/mistral vision — no token count available, estimate per page
    usd = n_pages * 0.0005   # rough — ~500 tokens per page at gemini flash price
    co2 = n_pages * _CO2_PER_VISION
    _calls().append({"type": "vision", "pages": n_pages, "usd": usd, "co2_g": co2})


def get_summary():
    calls     = _calls()
    total_usd = sum(c["usd"] for c in calls)
    total_co2 = sum(c["co2_g"] for c in calls)
    total_tok = sum(c.get("tokens", 0) for c in calls)
    return {
        "total_usd":    round(total_usd, 6),
        "total_co2_g":  round(total_co2, 4),
        "total_tokens": total_tok,
        "calls":        len(calls),
    }
