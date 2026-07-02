import base64
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

from .graph import graph
from . import cost

app = FastAPI(title="Orkester")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


class File(BaseModel):
    name: str
    mime: str
    data: str   # base64


class Req(BaseModel):
    text:         str        = ""
    files:        list[File] = []
    force_vision: bool       = False


@app.get("/")
@app.get("/health")
def health():
    return {"ok": True}


@app.post("/chat")
def chat(req: Req):
    if not req.text and not req.files:
        raise HTTPException(400, "send at least some text or a file")

    cost.reset()   # fresh counter per request

    file_inputs = [{
        "src":          f.name,
        "blob":         base64.b64decode(f.data),
        "mime":         f.mime,
        "force_vision": req.force_vision
    } for f in req.files]

    result = graph.invoke({
        "inputs":       file_inputs,
        "query":        req.text,
        "extracted":    [],
        "plan_trace":   [],
        "clarifying_q": None,
        "answer":       None,
    })

    return {
        "extracted":    result["extracted"],
        "plan_trace":   result["plan_trace"],
        "clarifying_q": result.get("clarifying_q"),
        "answer":       result.get("answer"),
        "usage":        cost.get_summary(),
    }
