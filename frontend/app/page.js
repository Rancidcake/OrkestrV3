"use client"

import { useState, useRef, useEffect } from "react"
import { Send, Paperclip, X, ChevronDown, ChevronRight } from "lucide-react"
import "../lib/firebase"

// backend calls go through Next.js rewrites — no cross-origin issues
const API = process.env.NEXT_PUBLIC_API_URL ?? ""

function toBase64(file) {
  return new Promise((res, rej) => {
    const r = new FileReader()
    r.onload  = () => res(r.result.split(",")[1])
    r.onerror = rej
    r.readAsDataURL(file)
  })
}

// FIXME: these colors were picked by eye, may need design review
function badgeClass(how, method) {
  const v = how ?? method ?? ""
  if (v === "native")      return "bg-emerald-50 text-emerald-700 border border-emerald-200"
  if (v === "ocr")         return "bg-amber-50 text-amber-700 border border-amber-200"
  if (v === "vision")      return "bg-blue-50 text-blue-700 border border-blue-200"
  if (v === "mistral-ocr") return "bg-violet-50 text-violet-700 border border-violet-200"
  if (v === "tess")        return "bg-stone-100 text-stone-500 border border-stone-200"
  if (v === "failed")      return "bg-red-50 text-red-500 border border-red-200"
  return "bg-stone-100 text-stone-500 border border-stone-200"
}

const STEP_ICON = { extract: "·", plan: "·", retrieve: "·", tool: "·", error: "·" }
const METHOD_COLOR = {
  native: "text-emerald-600", ocr: "text-amber-600", vision: "text-blue-600",
  "mistral-ocr": "text-violet-600", audio: "text-pink-600", youtube: "text-red-600",
  tess: "text-stone-500",
}

function PlanTrace({ trace }) {
  const [open, setOpen] = useState(false)
  if (!trace || !trace.length) return null

  // summary line — just tools used
  const toolSteps = trace.filter(t => t.step === "tool")
  const summary   = toolSteps.map(t => t.tool).join(" → ") || "processing"

  return (
    <div className="mt-1.5 px-1">
      <button
        onClick={() => setOpen(o => !o)}
        className="flex items-center gap-1.5 text-[11px] text-stone-400 hover:text-stone-600 transition-colors"
      >
        <span>{open ? "▾" : "▸"}</span>
        <span className="font-mono text-red-500">{summary}</span>
        <span className="text-stone-300">· {trace.length} steps</span>
      </button>

      {open && (
        <div className="mt-1.5 space-y-1 border-l-2 border-stone-100 pl-3">
          {trace.map((t, i) => (
            <div key={i} className="flex items-start gap-2 text-[11px]">
              <span className="shrink-0 mt-0.5">{STEP_ICON[t.step] ?? "·"}</span>
              <div className="min-w-0">
                {t.step === "extract" && (
                  <span>
                    <span className={`font-mono ${METHOD_COLOR[t.method] ?? "text-stone-500"}`}>{t.method}</span>
                    <span className="text-stone-400"> · {t.src}</span>
                    {t.ok
                      ? <span className="text-stone-400"> · {t.chars} chars</span>
                      : <span className="text-red-400"> · {t.err ?? "failed"}</span>
                    }
                  </span>
                )}
                {t.step === "plan" && (
                  <span className="text-stone-500">
                    classified as <span className="font-mono text-stone-700">{t.action}</span>
                    {t.tools && <span className="text-stone-400"> → [{t.tools.join(", ")}]</span>}
                    {t.question && <span className="text-stone-400"> → clarify</span>}
                  </span>
                )}
                {t.step === "retrieve" && (
                  <span className="text-stone-500">
                    BM25 retrieved <span className="font-mono text-stone-700">{t.chunks} chunks</span>
                    {t.sources?.length > 0 && (
                      <span className="text-stone-400"> from [{t.sources.join(", ")}]</span>
                    )}
                  </span>
                )}
                {t.step === "tool" && (
                  <span>
                    <span className="font-mono text-red-600">{t.tool}</span>
                    {t.sources?.length > 0 && (
                      <span className="text-stone-400"> · [{t.sources.join(", ")}]</span>
                    )}
                  </span>
                )}
              </div>
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function Extracted({ items }) {
  const [open, setOpen] = useState(false)
  if (!items.length) return null

  return (
    <div className="mt-1 border border-stone-200 rounded-xl bg-white overflow-hidden">
      <button
        onClick={() => setOpen(o => !o)}
        className="w-full flex items-center gap-2 px-3 py-2 text-xs text-stone-500 hover:bg-stone-50 transition-colors"
      >
        {open ? <ChevronDown size={12} /> : <ChevronRight size={12} />}
        <span className="font-medium text-stone-600">extracted</span>
        <span className="text-stone-400">
          {items.length} source{items.length !== 1 ? "s" : ""}
        </span>
      </button>

      {open && (
        <div className="border-t border-stone-100 px-3 pb-3 space-y-3">
          {items.map((r, i) => (
            <div key={i} className="pt-2">
              <div className="flex items-center gap-2 flex-wrap mb-1">
                <span className="text-[11px] font-mono text-stone-500 truncate max-w-[200px]">{r.src}</span>
                <span className={`text-[10px] px-1.5 py-0.5 rounded-full font-medium ${badgeClass(r.how, r.method)}`}>
                  {r.how ?? r.method ?? "ok"}
                </span>
                {r.secs && (
                  <span className="text-[10px] text-stone-400">
                    {Math.floor(r.secs / 60)}m {Math.floor(r.secs % 60)}s
                  </span>
                )}
                {r.pages && (
                  <span className="text-[10px] text-stone-400">{r.pages}p</span>
                )}
                {r.confidence != null && (
                  <span className="text-[10px] text-stone-400">conf {r.confidence}%</span>
                )}
              </div>
              {r.text && <p className="text-[11px] text-stone-400 line-clamp-3 leading-relaxed">{r.text}</p>}
              {r.err  && <p className="text-[11px] text-red-400">{r.err}</p>}
            </div>
          ))}
        </div>
      )}
    </div>
  )
}

function UsageBadge({ usage }) {
  if (!usage) return null
  const usd = usage.total_usd < 0.000001
    ? "<$0.000001"
    : `~$${usage.total_usd.toFixed(6)}`
  const co2 = usage.total_co2_g < 0.001
    ? "<0.001"
    : usage.total_co2_g.toFixed(3)
  return (
    <div className="flex items-center gap-2 mt-1.5 px-1 flex-wrap">
      <span className="text-[10px] text-stone-400">
        cost <span className="text-stone-600 font-medium">{usd}</span>
      </span>
      <span className="text-stone-300 text-[10px]">·</span>
      <span className="text-[10px] text-stone-400">
        carbon <span className="text-stone-600 font-medium">{co2} gCO₂e</span>
      </span>
      <span className="text-stone-300 text-[10px]">·</span>
      <span className="text-[10px] text-stone-400">
        <span className="text-stone-600 font-medium">{usage.total_tokens}</span> tokens
      </span>
    </div>
  )
}

function AgentBubble({ msg }) {
  return (
    <div className="flex flex-col gap-0.5 max-w-[82%]">
      <Extracted items={msg.extracted} />
      <PlanTrace trace={msg.plan_trace} />
      <div className="bg-white border border-stone-200 rounded-2xl rounded-tl-sm px-4 py-3 text-sm text-stone-800 whitespace-pre-wrap shadow-sm mt-1.5 leading-relaxed">
        {msg.clarifying_q ?? msg.answer ?? "…"}
      </div>
      <UsageBadge usage={msg.usage} />
    </div>
  )
}

// empty state suggestions — TODO: make these clickable to prefill input
const HINTS = [
  "Upload a PDF and ask a question about it",
  "Paste a YouTube URL to get a summary",
  "Upload an audio file to transcribe and summarize",
  "Upload two docs and ask me to compare them",
]

export default function Home() {
  const [messages, setMessages]       = useState([])
  const [text, setText]               = useState("")
  const [files, setFiles]             = useState([])
  const [loading, setLoading]         = useState(false)
  const [forceVision, setForceVision] = useState(false)
  const fileRef                       = useRef(null)
  const bottomRef                     = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: "smooth" })
  }, [messages, loading])

  async function pickFiles(e) {
    const picked  = Array.from(e.target.files ?? [])
    const encoded = await Promise.all(picked.map(async f => ({
      name: f.name,
      mime: f.type,
      data: await toBase64(f)
    })))
    setFiles(prev => [...prev, ...encoded])
    e.target.value = ""
  }

  async function send() {
    if (!text.trim() && !files.length) return
    setLoading(true)

    const userMsg = { role: "user", text, files: files.map(f => f.name) }
    setMessages(prev => [...prev, userMsg])

    try {
      const res  = await fetch(`${API}/chat`, {
        method:  "POST",
        headers: { "Content-Type": "application/json" },
        body:    JSON.stringify({ text, files, force_vision: forceVision })
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail ?? "request failed")
      setMessages(prev => [...prev, { role: "agent", ...data }])
    } catch (err) {
      setMessages(prev => [...prev, { role: "error", text: err.message }])
    }

    setText("")
    setFiles([])
    setForceVision(false)
    setLoading(false)
  }

  function onKey(e) {
    if (e.key === "Enter" && !e.shiftKey) { e.preventDefault(); send() }
  }

  const hasPdf = files.some(f => f.mime === "application/pdf")

  return (
    <div className="flex flex-col h-screen bg-stone-50 font-sans">

      {/* header */}
      <header className="bg-white border-b border-stone-200 px-5 py-3 flex items-center gap-3 shadow-sm">
        <div className="w-7 h-7 bg-red-500 rounded-lg flex items-center justify-center shrink-0">
          <span className="text-white text-xs font-bold tracking-tighter">OR</span>
        </div>
        <span className="font-semibold text-stone-800 tracking-wide text-sm">ORKESTER</span>
        <span className="ml-auto text-[11px] text-stone-400 hidden sm:block">
          multimodal agentic assistant
        </span>
      </header>

      {/* messages */}
      <div className="flex-1 overflow-y-auto px-4 py-6 space-y-5">

        {messages.length === 0 && (
          <div className="flex flex-col items-center justify-center h-full pb-10 text-center space-y-4">
            <div className="w-14 h-14 bg-red-500 rounded-2xl flex items-center justify-center shadow-md">
              <span className="text-white text-2xl font-bold">O</span>
            </div>
            <div>
              <p className="text-stone-700 font-semibold text-base">What can I help you with?</p>
              <p className="text-stone-400 text-xs mt-1">Accepts text, PDF, image, and audio — multiple at once</p>
            </div>
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-2 mt-2 max-w-md w-full">
              {HINTS.map((h, i) => (
                <div key={i} className="text-left text-xs text-stone-500 bg-white border border-stone-200 rounded-xl px-3 py-2.5 leading-relaxed">
                  {h}
                </div>
              ))}
            </div>
          </div>
        )}

        {messages.map((msg, i) => (
          <div key={i} className={`flex ${msg.role === "user" ? "justify-end" : "justify-start"}`}>

            {msg.role === "user" && (
              <div className="max-w-[72%] space-y-1">
                {msg.files.map((f, j) => (
                  <div key={j} className="flex justify-end">
                    <span className="inline-flex items-center gap-1 text-[11px] bg-red-50 border border-red-200 text-red-600 rounded-full px-2.5 py-0.5 font-mono">
                      {f}
                    </span>
                  </div>
                ))}
                {msg.text && (
                  <div className="bg-red-500 text-white rounded-2xl rounded-tr-sm px-4 py-2.5 text-sm shadow-sm leading-relaxed">
                    {msg.text}
                  </div>
                )}
              </div>
            )}

            {msg.role === "agent" && <AgentBubble msg={msg} />}

            {msg.role === "error" && (
              <div className="text-xs text-red-600 bg-red-50 border border-red-200 px-3 py-2 rounded-xl max-w-sm">
                {msg.text}
              </div>
            )}
          </div>
        ))}

        {loading && (
          <div className="flex justify-start">
            <div className="bg-white border border-stone-200 rounded-2xl rounded-tl-sm px-4 py-3 shadow-sm flex items-center gap-1">
              {[0, 150, 300].map(delay => (
                <span
                  key={delay}
                  className="block w-1.5 h-1.5 bg-red-400 rounded-full animate-bounce"
                  style={{ animationDelay: `${delay}ms` }}
                />
              ))}
            </div>
          </div>
        )}

        <div ref={bottomRef} />
      </div>

      {/* input area */}
      <div className="bg-white border-t border-stone-200 px-4 pt-3 pb-4 space-y-2">

        {files.length > 0 && (
          <div className="flex gap-2 flex-wrap">
            {files.map((f, i) => (
              <div key={i} className="flex items-center gap-1.5 bg-stone-50 border border-stone-200 rounded-full px-3 py-1 text-xs text-stone-600">
                <span className="max-w-[140px] truncate">{f.name}</span>
                <button
                  onClick={() => setFiles(prev => prev.filter((_, j) => j !== i))}
                  className="text-stone-300 hover:text-red-400 transition-colors"
                >
                  <X size={10} />
                </button>
              </div>
            ))}
          </div>
        )}

        {hasPdf && (
          <label className="flex items-center gap-2 text-xs text-stone-400 cursor-pointer select-none w-fit">
            <input
              type="checkbox"
              checked={forceVision}
              onChange={e => setForceVision(e.target.checked)}
              className="accent-red-500 rounded"
            />
            PDF is OCR-disabled (use vision model)
          </label>
        )}

        <div className="flex gap-2 items-end">
          <button
            onClick={() => fileRef.current?.click()}
            title="Attach file"
            className="p-2 text-stone-400 hover:text-red-500 hover:bg-red-50 rounded-lg transition-colors shrink-0"
          >
            <Paperclip size={18} />
          </button>

          <input
            ref={fileRef}
            type="file"
            multiple
            accept=".pdf,.jpg,.jpeg,.png,.mp3,.wav,.m4a"
            className="hidden"
            onChange={pickFiles}
          />

          <textarea
            value={text}
            onChange={e => setText(e.target.value)}
            onKeyDown={onKey}
            placeholder="Ask something or upload a file…"
            rows={1}
            className="flex-1 resize-none bg-stone-50 border border-stone-200 rounded-xl px-3 py-2.5 text-sm text-stone-800 placeholder-stone-400 outline-none focus:ring-2 focus:ring-red-300 focus:border-red-300 transition-all"
          />

          <button
            onClick={send}
            disabled={loading || (!text.trim() && !files.length)}
            className="p-2.5 bg-red-500 hover:bg-red-600 disabled:opacity-40 disabled:cursor-not-allowed text-white rounded-xl transition-colors shrink-0 shadow-sm"
          >
            <Send size={16} />
          </button>
        </div>
      </div>
    </div>
  )
}
