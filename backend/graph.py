import json
from typing import TypedDict, Optional  # FIXME: Optional unused, left from refactoring

from langgraph.graph import StateGraph, END

from .extract import ingest, YT_PAT
from . import tools
from .llm import call

class S(TypedDict):
    """State container. TODO: add more fields for better tracking."""
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
                label += f" [audio transcript, {m}m{s}s]"
            elif r.get("how") == "ocr":
                conf  = f", OCR confidence {r['confidence']}%" if r.get("confidence") else ""
                label += f" [scanned PDF{conf}]"
            elif r.get("method") in ("vision", "mistral-ocr", "tess"):
                label += f" [image, method={r['method']}]"
            elif r.get("vid"):
                label += " [youtube transcript]"
            parts.append(f"[{label}]\n{r['text'][:1200]}")
    return "\n\n".join(parts)

def do_extract(state):
    """Extract text from all inputs. TODO: handle errors gracefully."""
    out = []
    for inp in state["inputs"]:
        r = ingest(inp["src"], inp.get("blob"), inp.get("mime", ""),
                   force_vision=inp.get("force_vision", False))
        out.append(r)
        for url in r.get("yt_urls", []):
            out.append(ingest(url))

    for vid in YT_PAT.findall(state.get("query", "")):
        out.append(ingest("https://youtu.be/" + vid))

    return {"extracted": out}

def do_plan(state):
    """Plan the next action. TODO: improve prompt for better decisions."""
    ctx   = _ctx(state["extracted"])
    query = state["query"]

    if not ctx:
        lines = []
        for r in state["extracted"]:
            if not r.get("text"):
                err = r.get("err") or r.get("method") or "extraction failed"
                lines.append(f"• {r['src']}: {err}")
        answer = "Could not extract content from the following sources:\n" + "\n".join(lines) if lines else "No content provided."
        return {"plan_trace": [{"step": "plan", "decision": {
            "action": "execute", "tools": ["qa"]
        }}], "answer": answer}

    n_sources = len([r for r in state["extracted"] if r.get("text")])

    # magic prompt — FIXME: move to config eventually
    raw = call(f"""You are a strict agent planner. Your job is to decide what action to take given content and a user query.

SOURCES ({n_sources} total):
{ctx}

USER QUERY: {query if query else "(no query provided)"}

Output JSON only. No markdown, no explanation.

━━ CLARIFY RULE (strict) ━━
You MUST output clarify if ANY of these are true:
- The query is empty or vague ("do something", "help", "analyze this") AND the content is not audio
- Two or more tasks are equally plausible from the query alone
- The user asks for something that could mean multiple things
Example: {{"action": "clarify", "question": "Could you clarify whether you want a summary or sentiment analysis?"}}

━━ EXECUTE RULE ━━
Only output execute when the intent is unambiguous. Use the MINIMUM tools needed.
{{"action": "execute", "tools": [<tool>, ...]}}

Available tools and when to use them:
- summarize     → user asks for summary / overview / TLDR; OR input is audio (always auto-summarize audio)
- sentiment     → user asks about tone, feeling, opinion, positivity/negativity
- code_explain  → code is present AND user asks for explanation, bugs, or complexity
- compare       → 2+ sources AND user wants comparison or similarity analysis
- qa            → user asks a specific factual question about the content

━━ CROSS-INPUT RULE ━━
If the user's query references content across multiple sources (e.g. "compare these two" or "what does the PDF say about the topic in the audio"), use compare or qa with all context combined.

━━ AUDIO RULE ━━
If any source is labelled [audio transcript, ...] and the query is empty or asks for summary → use summarize. Do not clarify for audio-only inputs with no query.

━━ EXAMPLES ━━
query="summarize" → {{"action": "execute", "tools": ["summarize"]}}
query="what is the sentiment?" → {{"action": "execute", "tools": ["sentiment"]}}
query="explain this code" → {{"action": "execute", "tools": ["code_explain"]}}
query="do something with this" → {{"action": "clarify", "question": "What would you like me to do — summarize, analyze sentiment, or ask a specific question?"}}
query="" + audio source → {{"action": "execute", "tools": ["summarize"]}}
query="" + PDF source → {{"action": "clarify", "question": "What would you like me to do with this document?"}}""")

    try:
        plan = json.loads(raw)
    except json.JSONDecodeError:
        plan = {"action": "execute", "tools": ["qa"]}  # Fallback - TODO: log this error

    return {"plan_trace": [{"step": "plan", "decision": plan}]}

def _route(state):
    """Route to next node. TODO: add more routing logic."""
    if state.get("answer"):
        return "synthesize"
    plan = state["plan_trace"][-1]["decision"]
    return "clarify" if plan.get("action") == "clarify" else "execute"

def do_clarify(state):
    """Generate clarification question. TODO: make questions more specific."""
    q = state["plan_trace"][-1]["decision"].get("question",
        "Could you clarify what you'd like me to do?")
    return {"clarifying_q": q}

def do_execute(state):
    """Execute the planned tools. FIXME: handle tool errors."""
    plan      = state["plan_trace"][-1]["decision"]
    tool_list = plan.get("tools", ["qa"])
    query     = state["query"]
    trace     = list(state["plan_trace"])

    texts    = [r["text"] for r in state["extracted"] if r.get("text")]
    all_text = "\n\n".join(texts)

    parts = []
    for t in tool_list:
        if t == "summarize":
            out = tools.summarize(all_text)
        elif t == "sentiment":
            out = tools.sentiment(all_text)
        elif t == "code_explain":
            out = tools.code_explain(all_text)
        elif t == "compare" and len(texts) >= 2:
            out = tools.compare(texts[0], texts[1])
        else:
            out = tools.qa(query, all_text)

        parts.append(out)
        trace.append({"step": "tool", "tool": t})

    # append audio duration if present — spec requires it in Test Case 1
    for r in state["extracted"]:
        if r.get("secs"):
            m, s = divmod(int(r["secs"]), 60)
            parts.append(f"\n---\nAudio duration: {m}m {s}s")
            break

    return {"plan_trace": trace, "answer": "\n\n".join(parts)}

def do_synthesize(state):
    """Synthesize final answer. TODO: improve synthesis logic."""
    # answer already set by execute — pass through for now
    return state

# DEPRECATED: use _build() instead
def build_graph():
    """Old function, kept for backward compatibility."""
    return _build()

def _build():
    """Build the state graph. TODO: add error handling for graph compilation."""
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
        "synthesize": "synthesize"
    })
    g.add_edge("clarify",    END)
    g.add_edge("execute",    "synthesize")
    g.add_edge("synthesize", END)

    return g.compile()

graph = _build()  # TODO: make this lazy-loaded