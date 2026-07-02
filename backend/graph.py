import re
from typing import TypedDict, Optional  # FIXME: Optional unused, left from refactoring

from langgraph.graph import StateGraph, END

from .extract import ingest, YT_PAT
from . import tools
from .llm import call


class S(TypedDict):
    inputs:       list
    query:        str
    extracted:    list
    plan_trace:   list
    clarifying_q: str | None
    answer:       str | None


def _ctx(extracted):
    parts = []
    for r in extracted:
        if r.get("text"):
            label = r["src"]
            if r.get("secs"):
                m, s = divmod(int(r["secs"]), 60)
                label += f" [audio, {m}m{s}s]"
            elif r.get("how") == "ocr":
                conf   = f", conf {r['confidence']}%" if r.get("confidence") else ""
                label += f" [scanned PDF{conf}]"
            elif r.get("method") in ("vision", "mistral-ocr", "tess"):
                label += f" [image/{r['method']}]"
            elif r.get("vid"):
                label += " [youtube]"
            parts.append(f"[{label}]\n{r['text'][:1200]}")
    return "\n\n".join(parts)


def do_extract(state):
    out    = list(state.get("extracted", []))   # preserve pre-populated (used in tests)
    events = []

    for inp in state["inputs"]:
        r = ingest(inp["src"], inp.get("blob"), inp.get("mime", ""),
                   force_vision=inp.get("force_vision", False))
        out.append(r)

        method = r.get("how") or r.get("method") or ("audio" if r.get("secs") else "text")
        events.append({
            "step":   "extract",
            "src":    r["src"],
            "method": method,
            "chars":  len(r.get("text") or ""),
            "ok":     bool(r.get("text")),
            "err":    r.get("err"),
        })

        # follow YouTube URLs embedded inside PDFs
        for url in r.get("yt_urls", []):
            yt = ingest(url)
            out.append(yt)
            events.append({
                "step":   "extract",
                "src":    url,
                "method": "youtube",
                "chars":  len(yt.get("text") or ""),
                "ok":     bool(yt.get("text")),
            })

    # YouTube URLs in the query text
    for vid in YT_PAT.findall(state.get("query", "")):
        url = "https://youtu.be/" + vid
        yt  = ingest(url)
        out.append(yt)
        events.append({
            "step":   "extract",
            "src":    url,
            "method": "youtube",
            "chars":  len(yt.get("text") or ""),
            "ok":     bool(yt.get("text")),
        })

    return {"extracted": out, "plan_trace": events}


def _classify(query, extracted):
    """
    Rule-based intent classifier — zero LLM calls.
    Deterministic: same inputs always produce same output.
    Returns (action, tools_list | clarify_question).
    """
    q         = query.lower().strip()
    texts     = [r for r in extracted if r.get("text")]
    has_audio = any(r.get("secs") for r in texts)
    n_sources = len(texts)

    if has_audio and not q:
        return "execute", ["summarize"]

    if not q:
        return "clarify", "What would you like me to do — summarize, ask a question, analyze sentiment, or explain code?"

    _vague = {"do something", "help", "analyze this", "process this",
               "what do you think", "anything", "go ahead"}
    if q in _vague or q.rstrip("?!.") in _vague:
        return "clarify", "Could you clarify — summary, sentiment analysis, or a specific question?"

    if re.search(r"\b(summar|tldr|overview|brief|outline|key points?)\b", q):
        return "execute", ["summarize"]

    if re.search(r"\b(sentiment|tone|feeling|emotion|positive|negative|opinion|mood)\b", q):
        return "execute", ["sentiment"]

    if re.search(r"\b(explain|what does|how does|bug|error|complexity|time complex|space complex)\b", q):
        all_text = " ".join(r.get("text", "") for r in texts)
        if re.search(r"(def |class |function |import |=>|\bvar\b|\bconst\b|=>|{)", all_text):
            return "execute", ["code_explain"]

    if re.search(r"\b(compar|differ|similar|versus|vs\.?|contrast|same topic|both)\b", q) and n_sources >= 2:
        return "execute", ["compare"]

    return "execute", ["qa"]


def do_plan(state):
    ctx   = _ctx(state["extracted"])
    query = state["query"]
    trace = list(state["plan_trace"])   # carry forward extraction events

    if not ctx:
        if query:
            # pure conversational QA — no files, just a question
            trace.append({"step": "plan", "action": "execute", "tools": ["qa"]})
            return {"plan_trace": trace}
        lines  = [f"• {r['src']}: {r.get('err') or 'extraction failed'}"
                  for r in state["extracted"] if not r.get("text")]
        answer = "Could not extract content:\n" + "\n".join(lines) if lines else "No content provided."
        trace.append({"step": "plan", "action": "error"})
        return {"plan_trace": trace, "answer": answer}

    action, payload = _classify(query, state["extracted"])
    trace.append({"step": "plan", "action": action,
                  "tools": payload if action == "execute" else None,
                  "question": payload if action == "clarify" else None})
    return {"plan_trace": trace}


def _route(state):
    if state.get("answer"):
        return "synthesize"
    last = next((t for t in reversed(state["plan_trace"]) if t["step"] == "plan"), {})
    return "clarify" if last.get("action") == "clarify" else "execute"


def do_clarify(state):
    last = next((t for t in reversed(state["plan_trace"]) if t["step"] == "plan"), {})
    q    = last.get("question", "Could you clarify what you'd like me to do?")
    return {"clarifying_q": q}


def do_execute(state):
    last      = next(t for t in reversed(state["plan_trace"]) if t["step"] == "plan")
    tool_list = last.get("tools", ["qa"])
    query     = state["query"]
    trace     = list(state["plan_trace"])

    srcs     = [{"src": r["src"], "text": r["text"]}
                for r in state["extracted"] if r.get("text")]
    all_text = "\n\n".join(s["text"] for s in srcs)
    texts    = [s["text"] for s in srcs]

    parts = []
    for t in tool_list:
        if t == "summarize":
            out = tools.summarize(all_text)
            trace.append({"step": "tool", "tool": "summarize",
                          "sources": [s["src"] for s in srcs]})

        elif t == "sentiment":
            out = tools.sentiment(all_text)
            trace.append({"step": "tool", "tool": "sentiment",
                          "sources": [s["src"] for s in srcs]})

        elif t == "code_explain":
            out = tools.code_explain(all_text)
            trace.append({"step": "tool", "tool": "code_explain",
                          "sources": [s["src"] for s in srcs]})

        elif t == "compare" and len(texts) >= 2:
            out = tools.compare(texts[0], texts[1])
            trace.append({"step": "tool", "tool": "compare",
                          "sources": [srcs[0]["src"], srcs[1]["src"]]})

        else:
            answer, retrieve_log = tools.qa(query, sources=srcs)
            out = answer
            # log BM25 retrieval separately
            trace.append({"step": "retrieve", "tool": "BM25",
                          "chunks": len(retrieve_log),
                          "sources": list({r["src"] for r in retrieve_log})})
            trace.append({"step": "tool", "tool": "qa",
                          "sources": [s["src"] for s in srcs]})

        parts.append(out)

    # audio duration footer
    for r in state["extracted"]:
        if r.get("secs"):
            m, s = divmod(int(r["secs"]), 60)
            parts.append(f"\n---\nAudio duration: {m}m {s}s")
            break

    return {"plan_trace": trace, "answer": "\n\n".join(parts)}


def do_synthesize(state):
    return state


# DEPRECATED: use _build() instead
def build_graph():
    return _build()


def _build():
    g = StateGraph(S)
    g.add_node("extract",    do_extract)
    g.add_node("plan",       do_plan)
    g.add_node("clarify",    do_clarify)
    g.add_node("execute",    do_execute)
    g.add_node("synthesize", do_synthesize)

    g.set_entry_point("extract")
    g.add_edge("extract", "plan")
    g.add_conditional_edges("plan", _route, {
        "clarify":    "clarify",
        "execute":    "execute",
        "synthesize": "synthesize",
    })
    g.add_edge("clarify",    END)
    g.add_edge("execute",    "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()


graph = _build()
