import { useCallback, useEffect, useRef, useState } from "react";
import { ArrowUp, Download, Mic, RefreshCw, SlidersHorizontal, Sparkles, Square, Volume2, VolumeX, X } from "lucide-react";
import { api } from "../api/client";
import { ALERT_LEVELS, SPEAK_UP_LEVELS } from "../alerts";
import { formatWh, peso } from "../format";
import { canListen, canSpeak, createSpeaker, listen, stopSpeaking } from "../speech";
import Figures from "./Figures";

/**
 * Kilo, the on-device assistant: a small model in Ollama that says what the dashboard's
 * numbers mean. Ask by typing or by voice; it also speaks up by itself when a new alert
 * comes in (a bubble over the button, a desktop notification, and aloud if voice is on).
 */

const PREFS_KEY = "kilowhat-assistant";
const ANNOUNCED_KEY = "kilowhat-announced";
const ANNOUNCE_AGAIN_MS = 12 * 3600 * 1000; // an alert that's still there is mentioned again after this
const BUBBLE_MS = 20000;
const WARM_EVERY_MS = 50000; // the backend keeps the same facts for 60 s
const DEFAULT_PREFS = { speak: false, autoBrief: true, notify: false };

const SUGGESTIONS = {
  dashboard: ["Is AI making my bill go up?", "What's using power right now?", "Ano ang dapat kong gawin para makatipid?"],
  device: ["What's using power right now?", "Is this reading measured or estimated?", "What does “loaded” mean?"],
  analytics: ["Will I stay under my budget?", "How much does AI add to my bill?", "How much is AI over a year?"],
  models: ["Which model costs me the most?", "Why does a local model cost more than a cloud one?"],
  carbon: ["Is my AI carbon footprint a lot?", "Where does my CO₂ come from?", "Is it going up or down?", "How can I lower my AI carbon footprint?"],
  recommendations: ["Which recommendation should I do first?", "How much can I save a month?"],
};

const SETUP = {
  ollama_missing: { title: "Install Ollama to turn me on", action: "download" },
  ollama_stopped: { title: "Ollama isn't running", action: "retry" },
  model_missing: { title: "One download to go", action: "pull" },
};

const readStore = (key, fallback) => {
  try {
    const v = JSON.parse(localStorage.getItem(key));
    return v && typeof v === "object" ? { ...fallback, ...v } : fallback;
  } catch {
    return fallback;
  }
};

const writeStore = (key, value) => {
  try {
    localStorage.setItem(key, JSON.stringify(value));
  } catch {
    // Private mode: preferences last for this session only
  }
};

let lastId = 0;
const nextId = () => ++lastId;

export default function Assistant({ params, range, view, alerts = [], askRequest, onOpenView }) {
  const [open, setOpen] = useState(false);
  const [status, setStatus] = useState(null);
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState("");
  const [busy, setBusy] = useState(false);
  const [listening, setListening] = useState(false);
  const [prefs, setPrefs] = useState(() => readStore(PREFS_KEY, DEFAULT_PREFS));
  const [settingsOpen, setSettingsOpen] = useState(false);
  const [pull, setPull] = useState(null);
  const [bubble, setBubble] = useState(null);
  const [unread, setUnread] = useState(false);

  // Callbacks run from timers and streams, so they read the current values from here.
  const latest = useRef({});
  latest.current = { params, range, view, prefs, status, open, messages, alerts };
  const busyRef = useRef(false);
  const abortRef = useRef(null);
  const speakerRef = useRef(null);
  const stopListeningRef = useRef(null);
  const pendingBrief = useRef([]);
  const warmedAt = useRef(0);
  const endRef = useRef(null);
  const inputRef = useRef(null);

  const ready = status?.state === "ready";

  const refreshStatus = useCallback(() => {
    api.assistantStatus(latest.current.params).then(setStatus).catch(() => setStatus({ state: "backend_down" }));
  }, []);

  useEffect(() => {
    refreshStatus();
    const timer = setInterval(refreshStatus, 30000);
    return () => clearInterval(timer);
  }, [refreshStatus]);

  const savePrefs = (change) => {
    setPrefs((p) => {
      const next = { ...p, ...change };
      writeStore(PREFS_KEY, next);
      return next;
    });
  };

  const update = (id, change) => setMessages((ms) => ms.map((m) => (m.id === id ? { ...m, ...change } : m)));

  // One reply: to a question (text), or a briefing on alerts (brief = their ids). Returns its text.
  const ask = useCallback(async ({ text, brief, spoken = false }) => {
    if (busyRef.current) return null;
    busyRef.current = true;
    setBusy(true);
    const { params: p, range: r, view: v, prefs: pr, messages: before, alerts: current } = latest.current;
    const history = before.filter((m) => m.content && !m.error).map(({ role, content }) => ({ role, content }));
    const question = text ? { id: nextId(), role: "user", content: text } : null;
    if (question) history.push({ role: "user", content: text });
    const reply = {
      id: nextId(), role: "assistant", content: "", streaming: true,
      brief: brief ? current.filter((a) => brief.includes(a.id)) : null,
    };
    setMessages((ms) => [...ms, ...(question ? [question] : []), reply]);

    speakerRef.current?.cancel();
    const speaker = canSpeak && (spoken || pr.speak) ? createSpeaker() : null;
    speakerRef.current = speaker;
    const controller = new AbortController();
    abortRef.current = controller;
    let full = "";
    try {
      await api.assistantChat(p, { messages: history, view: v, range: r, brief }, (e) => {
        if (e.type === "delta") {
          full += e.text;
          speaker?.push(e.text);
          update(reply.id, { content: full });
        } else if (e.type === "done") {
          update(reply.id, { stats: e.stats });
        } else if (e.type === "error") {
          throw new Error(e.error);
        }
      }, controller.signal);
      speaker?.flush();
    } catch (err) {
      controller.abort(); // an error event mid-reply: close the stream
      if (err.name !== "AbortError") {
        update(reply.id, { error: err.message });
        if (err.state) refreshStatus();
      }
      full = null;
    } finally {
      update(reply.id, { streaming: false });
      abortRef.current = null;
      busyRef.current = false;
      setBusy(false);
    }
    return full;
  }, [refreshStatus]);

  const stop = () => {
    abortRef.current?.abort();
    speakerRef.current?.cancel();
  };

  const send = (text, spoken = false) => {
    const q = text.trim();
    if (!q || busyRef.current) return;
    setInput("");
    ask({ text: q, spoken });
  };

  // --- Speaking up by itself ---------------------------------------------------

  const announce = useCallback(async (ids) => {
    const { status: st, open: isOpen, prefs: pr, alerts: current } = latest.current;
    const chosen = current.filter((a) => ids.includes(a.id));
    if (!chosen.length) return;
    let text;
    if (st?.state === "ready") {
      text = await ask({ brief: ids });
    }
    if (!text) {
      // No model to put it into words: pass the alert on as it is.
      text = `${chosen[0].title}. ${chosen[0].text}`;
      if (st?.state !== "ready") {
        setMessages((ms) => [...ms, { id: nextId(), role: "assistant", content: text, brief: chosen }]);
      }
    }
    if (!isOpen) {
      setBubble({ text, level: chosen[0].level, count: chosen.length });
      setUnread(true);
    }
    if (pr.notify && document.hidden && typeof Notification !== "undefined" && Notification.permission === "granted") {
      const n = new Notification(`Kilo · ${chosen[0].title}`, { body: text.slice(0, 220), tag: chosen[0].id });
      n.onclick = () => {
        window.focus();
        setOpen(true);
        n.close();
      };
    }
  }, [ask]);

  // New alerts worth mentioning: brief on them once (again after ANNOUNCE_AGAIN_MS if still there).
  useEffect(() => {
    if (!prefs.autoBrief || !status || status.state === "backend_down") return;
    const seen = readStore(ANNOUNCED_KEY, {});
    const now = Date.now();
    const fresh = alerts.filter((a) => SPEAK_UP_LEVELS.has(a.level) && !(now - (seen[a.id] || 0) < ANNOUNCE_AGAIN_MS));
    if (!fresh.length) return;
    fresh.forEach((a) => (seen[a.id] = now));
    writeStore(ANNOUNCED_KEY, seen);
    pendingBrief.current.push(...fresh.map((a) => a.id));
    if (!busyRef.current) {
      const ids = pendingBrief.current.splice(0);
      announce(ids);
    }
  }, [alerts, prefs.autoBrief, status, announce]);

  // A briefing that came in while a reply was being written.
  useEffect(() => {
    if (!busy && pendingBrief.current.length) announce(pendingBrief.current.splice(0));
  }, [busy, announce]);

  useEffect(() => {
    if (!bubble) return;
    const timer = setTimeout(() => setBubble(null), BUBBLE_MS);
    return () => clearTimeout(timer);
  }, [bubble]);

  // --- Opening, warming up, asking from elsewhere -------------------------------

  const openPanel = useCallback(() => {
    setOpen(true);
    setBubble(null);
    setUnread(false);
  }, []);

  useEffect(() => {
    if (!open) return;
    refreshStatus();
    inputRef.current?.focus();
  }, [open, refreshStatus]);

  // While the user types, the model loads and reads the facts, so the reply starts sooner.
  useEffect(() => {
    if (!open || !ready || Date.now() - warmedAt.current < WARM_EVERY_MS) return;
    warmedAt.current = Date.now();
    api.assistantWarm(params, { view, range }).catch(() => {});
  }, [open, ready, params, view, range]);

  useEffect(() => {
    if (!askRequest) return;
    openPanel();
    ask({ text: askRequest.text });
  }, [askRequest, openPanel, ask]);

  useEffect(() => {
    endRef.current?.scrollIntoView({ block: "end" });
  }, [messages, open]);

  useEffect(() => {
    if (!open) return;
    const onKey = (e) => e.key === "Escape" && setOpen(false);
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open]);

  // Stop talking and listening when the page goes away.
  useEffect(() => () => {
    abortRef.current?.abort();
    stopListeningRef.current?.();
    stopSpeaking();
  }, []);

  // --- Voice ---------------------------------------------------------------------

  const toggleListening = () => {
    if (listening) {
      stopListeningRef.current?.();
      return;
    }
    speakerRef.current?.cancel();
    let heard = "";
    setListening(true);
    try {
      stopListeningRef.current = listen({
        onText: (text) => {
          heard = text;
          setInput(text);
        },
        onEnd: () => {
          setListening(false);
          stopListeningRef.current = null;
          if (heard.trim()) send(heard, true);
        },
        onError: (error) => {
          if (error === "not-allowed" || error === "service-not-allowed") {
            setMessages((ms) => [...ms, { id: nextId(), role: "assistant", content: "",
              error: "The browser didn't allow the microphone. Allow it in the address bar, or type your question." }]);
          }
        },
      });
    } catch {
      setListening(false);
    }
  };

  const toggleNotify = async () => {
    if (prefs.notify) return savePrefs({ notify: false });
    if (typeof Notification === "undefined") return;
    const permission = Notification.permission === "default" ? await Notification.requestPermission() : Notification.permission;
    savePrefs({ notify: permission === "granted" });
  };

  // --- Model download --------------------------------------------------------------

  const startPull = async () => {
    setPull({ status: "starting", completed: 0, total: 0 });
    try {
      await api.assistantPull((e) => {
        if (e.type === "progress") setPull((p) => ({ ...p, ...e, completed: e.completed ?? p.completed, total: e.total ?? p.total }));
        else if (e.type === "error") throw new Error(e.error);
      });
      setPull(null);
    } catch (err) {
      setPull({ error: err.message });
    }
    refreshStatus();
  };

  // --- Render ----------------------------------------------------------------------

  const suggestions = SUGGESTIONS[view] || SUGGESTIONS.dashboard;
  const setup = status && SETUP[status.state];

  return (
    <>
      {!open && bubble && (
        <div role="status" className="fixed z-30 bottom-[4.5rem] right-4 sm:bottom-20 sm:right-6 w-[min(22rem,calc(100vw-2rem))] dash-card shadow-pop p-3 animate-pop-in">
          <div className="flex items-start gap-2.5">
            <div className="w-7 h-7 rounded-full border border-line bg-sunken text-accent flex items-center justify-center shrink-0">
              <Sparkles className="w-3.5 h-3.5" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <span className="text-xs font-semibold text-ink">Kilo</span>
                <span className={`tech-tag ${ALERT_LEVELS[bubble.level]?.tag}`}>
                  {bubble.count > 1 ? `${bubble.count} new` : ALERT_LEVELS[bubble.level]?.label}
                </span>
              </div>
              <p className="text-sm text-ink-soft leading-relaxed line-clamp-4"><Figures text={bubble.text} /></p>
              <button onClick={openPanel} className="link mt-1.5">Ask a follow-up</button>
            </div>
            <button onClick={() => setBubble(null)} className="btn-icon -mr-1 -mt-1 shrink-0" aria-label="Dismiss">
              <X className="w-3.5 h-3.5" />
            </button>
          </div>
        </div>
      )}

      {!open && (
        <button
          onClick={openPanel}
          className="fixed z-30 bottom-4 right-4 sm:bottom-6 sm:right-6 inline-flex items-center gap-2 h-11 pl-3.5 pr-4 rounded-full bg-accent text-accent-on text-sm font-semibold shadow-pop transition-opacity hover:opacity-90"
          aria-label={`Ask Kilo, your energy assistant${unread ? " (new message)" : ""}`}
        >
          <Sparkles className="w-4 h-4" />
          <span>Ask Kilo</span>
          {unread && <span className="w-2 h-2 rounded-full bg-warn ring-2 ring-accent" />}
        </button>
      )}

      {open && (
        <section
          role="dialog"
          aria-label="Kilo, your energy assistant"
          className="fixed z-40 inset-0 sm:inset-auto sm:bottom-6 sm:right-6 sm:w-[25rem] sm:h-[min(40rem,calc(100vh-3rem))] flex flex-col bg-surface border border-line sm:rounded-xl shadow-pop animate-pop-in"
        >
          {/* Header */}
          <header className="flex items-center gap-2.5 px-4 h-14 border-b border-line shrink-0">
            <div className="w-8 h-8 rounded-full border border-line bg-sunken text-accent flex items-center justify-center shrink-0">
              <Sparkles className="w-4 h-4" />
            </div>
            <div className="min-w-0 flex-1">
              <div className="card-title">Kilo</div>
              <div className="card-sub truncate">
                {ready ? `On this computer · ${status.model}` : "On-device energy assistant"}
              </div>
            </div>
            {canSpeak && (
              <button
                onClick={() => {
                  if (prefs.speak) stopSpeaking();
                  savePrefs({ speak: !prefs.speak });
                }}
                className={`btn-icon ${prefs.speak ? "text-accent" : ""}`}
                aria-pressed={prefs.speak}
                title={prefs.speak ? "Reading replies aloud" : "Read replies aloud"}
                aria-label="Read replies aloud"
              >
                {prefs.speak ? <Volume2 className="w-4 h-4" /> : <VolumeX className="w-4 h-4" />}
              </button>
            )}
            <button
              onClick={() => setSettingsOpen((s) => !s)}
              className={`btn-icon ${settingsOpen ? "bg-sunken text-ink" : ""}`}
              aria-expanded={settingsOpen}
              aria-label="Assistant settings"
            >
              <SlidersHorizontal className="w-4 h-4" />
            </button>
            <button onClick={() => setOpen(false)} className="btn-icon" aria-label="Close assistant">
              <X className="w-4 h-4" />
            </button>
          </header>

          {settingsOpen && (
            <div className="px-4 py-3 border-b border-line bg-sunken space-y-2.5 text-sm shrink-0">
              <Toggle
                label="Speak up about new alerts"
                hint="Budget overruns and savings, in a bubble over the button"
                checked={prefs.autoBrief}
                onChange={() => savePrefs({ autoBrief: !prefs.autoBrief })}
              />
              {canSpeak && (
                <Toggle
                  label="Read replies aloud"
                  hint="Replies to spoken questions are always read aloud"
                  checked={prefs.speak}
                  onChange={() => savePrefs({ speak: !prefs.speak })}
                />
              )}
              {typeof Notification !== "undefined" && (
                <Toggle
                  label="Desktop notifications"
                  hint={Notification.permission === "denied" ? "Blocked in this browser's site settings" : "When this tab is in the background"}
                  checked={prefs.notify}
                  onChange={toggleNotify}
                />
              )}
              <div className="flex items-center justify-between gap-3 pt-1">
                <span className="text-xs text-ink-muted">
                  {canListen ? "Voice input uses your browser's speech recognition (Chrome sends audio to Google)." : "This browser has no speech recognition: type your questions."}
                </span>
                <button onClick={() => setMessages([])} className="btn shrink-0" disabled={!messages.length || busy}>
                  Clear chat
                </button>
              </div>
            </div>
          )}

          {/* Conversation */}
          <div className="flex-1 overflow-y-auto px-4 py-4 space-y-3" aria-live="polite">
            {setup && (
              <SetupCard status={status} setup={setup} pull={pull} onPull={startPull} onRetry={refreshStatus} />
            )}
            {status?.state === "backend_down" && (
              <p className="text-sm text-neg">Can't reach the backend on port 5001. Is it running?</p>
            )}

            {!messages.length && !setup && (
              <div className="space-y-3">
                <p className="text-sm text-ink-soft leading-relaxed">
                  Hi, I'm Kilo. Ask me what your power, bill or carbon numbers mean, and what to do about them. I run on
                  this computer, so nothing you ask leaves it.
                </p>
                <div className="flex flex-wrap gap-1.5">
                  {suggestions.map((s) => (
                    <button key={s} onClick={() => send(s)} disabled={!ready || busy} className="btn rounded-full text-left">
                      {s}
                    </button>
                  ))}
                </div>
              </div>
            )}

            {messages.map((m) => (
              <Message key={m.id} message={m} onOpenView={onOpenView} />
            ))}
            <div ref={endRef} />
          </div>

          {/* Composer */}
          <form
            onSubmit={(e) => {
              e.preventDefault();
              send(input);
            }}
            className="px-3 pt-3 pb-2 border-t border-line shrink-0"
          >
            <div className="flex items-center gap-1.5">
              <input
                ref={inputRef}
                value={input}
                onChange={(e) => setInput(e.target.value)}
                placeholder={listening ? "Listening…" : ready ? "Ask about your power, bill or CO₂" : "The assistant isn't ready yet"}
                disabled={!ready}
                aria-label="Ask Kilo"
                className="flex-1 min-w-0 h-9 rounded-lg border border-line bg-surface px-3 text-sm text-ink placeholder:text-ink-muted focus:border-accent focus:outline-none disabled:opacity-60"
              />
              {canListen && (
                <button
                  type="button"
                  onClick={toggleListening}
                  disabled={!ready || busy}
                  className={`btn-icon h-9 w-9 ${listening ? "bg-sunken text-neg hover:text-neg" : ""}`}
                  aria-pressed={listening}
                  aria-label={listening ? "Stop listening" : "Ask by voice"}
                  title={listening ? "Stop listening" : "Ask by voice"}
                >
                  <Mic className="w-4 h-4" />
                </button>
              )}
              {busy ? (
                <button type="button" onClick={stop} className="btn-primary h-9 w-9 px-0" aria-label="Stop the reply">
                  <Square className="w-3.5 h-3.5" />
                </button>
              ) : (
                <button type="submit" disabled={!ready || !input.trim()} className="btn-primary h-9 w-9 px-0" aria-label="Send">
                  <ArrowUp className="w-4 h-4" />
                </button>
              )}
            </div>
            <p className="mt-2 text-[11px] text-ink-muted leading-snug tabular-nums">
              A small model on this computer: check figures on the dashboard.
              {status?.energy?.kwh_30d > 0 &&
                ` Its replies used ${formatWh(status.energy.kwh_30d * 1000)} (${peso(status.energy.cost_30d)}) in 30 days.`}
            </p>
          </form>
        </section>
      )}
    </>
  );
}

function Message({ message: m, onOpenView }) {
  if (m.role === "user") {
    return (
      <div className="ml-auto max-w-[85%] w-fit rounded-xl rounded-br-sm bg-accent text-accent-on px-3 py-2 text-sm leading-relaxed whitespace-pre-wrap">
        {m.content}
      </div>
    );
  }
  const first = m.brief?.[0];
  return (
    <div className="max-w-[92%] space-y-1">
      {first && (
        <div className="flex flex-wrap items-center gap-1.5">
          <span className={`tech-tag ${ALERT_LEVELS[first.level]?.tag}`}>
            {m.brief.length > 1 ? `${m.brief.length} new alerts` : ALERT_LEVELS[first.level]?.label}
          </span>
          {onOpenView && first.view && (
            <button onClick={() => onOpenView(first.view)} className="link">Show me</button>
          )}
        </div>
      )}
      {(m.content || m.streaming) && (
        <div className="w-fit rounded-xl rounded-bl-sm border border-line bg-sunken px-3 py-2 text-sm text-ink leading-relaxed whitespace-pre-wrap">
          {m.content ? <Figures text={m.content} /> : <span className="text-ink-muted">Thinking…</span>}
        </div>
      )}
      {m.error && <p className="text-sm text-neg leading-relaxed">{m.error}</p>}
      {m.stats && !m.streaming && (
        <div className="text-[11px] text-ink-muted tabular-nums">
          {m.stats.first_word_seconds != null && `First word in ${m.stats.first_word_seconds.toFixed(1)} s · `}
          {m.stats.tokens} tokens{m.stats.tokens_per_second ? ` at ${m.stats.tokens_per_second} per second` : ""}
        </div>
      )}
    </div>
  );
}

function SetupCard({ status, setup, pull, onPull, onRetry }) {
  const pct = pull?.total ? Math.round((pull.completed / pull.total) * 100) : null;
  return (
    <div className="inset-panel p-3.5 space-y-2.5">
      <div className="text-sm font-semibold text-ink">{setup.title}</div>
      <p className="text-sm text-ink-soft leading-relaxed">{status.hint}</p>
      {setup.action === "download" && (
        <a href="https://ollama.com/download" target="_blank" rel="noreferrer" className="btn-primary w-fit">
          <Download className="w-3.5 h-3.5" />
          <span>Get Ollama</span>
        </a>
      )}
      {setup.action === "retry" && (
        <button onClick={onRetry} className="btn">
          <RefreshCw className="w-3.5 h-3.5" />
          <span>Check again</span>
        </button>
      )}
      {setup.action === "pull" && !pull && (
        <button onClick={onPull} className="btn-primary">
          <Download className="w-3.5 h-3.5" />
          <span>Download {status.model} (a few GB)</span>
        </button>
      )}
      {pull && !pull.error && (
        <div className="space-y-1.5">
          <div className="h-1.5 rounded-full bg-line overflow-hidden">
            <div className="h-full bg-accent transition-all" style={{ width: `${pct ?? 0}%` }} />
          </div>
          <div className="text-xs text-ink-muted tabular-nums">
            {pull.status}{pct != null ? ` · ${pct}%` : ""}
          </div>
        </div>
      )}
      {pull?.error && <p className="text-sm text-neg">{pull.error}</p>}
    </div>
  );
}

function Toggle({ label, hint, checked, onChange }) {
  return (
    <label className="flex items-start justify-between gap-3 cursor-pointer">
      <span className="min-w-0">
        <span className="block text-sm text-ink">{label}</span>
        <span className="block text-xs text-ink-muted">{hint}</span>
      </span>
      <input type="checkbox" checked={checked} onChange={onChange} className="mt-1 h-4 w-4 shrink-0 accent-accent" />
    </label>
  );
}
