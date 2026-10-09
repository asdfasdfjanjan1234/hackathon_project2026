import { useCallback, useEffect, useRef, useState } from "react";
import { RefreshCw, Sparkles, Square, Volume2 } from "lucide-react";
import { api } from "../api/client";
import { canSpeak, createSpeaker, stopSpeaking } from "../speech";
import Figures from "./Figures";

/**
 * Kilo's take on one view, written into the page instead of the chat panel. It runs only when
 * asked (each reply costs energy on this computer), streams in as the model writes it, and is
 * kept for the same figures (`cacheKey`) so leaving the view and coming back doesn't re-run it.
 */

const cache = new Map(); // cacheKey -> {text, stats}

export default function KiloInsight({ params, range, view, question, cacheKey, followUps = [], onAsk }) {
  const saved = cache.get(cacheKey);
  const [text, setText] = useState(saved?.text || "");
  const [stats, setStats] = useState(saved?.stats || null);
  const [state, setState] = useState(saved ? "done" : "idle"); // idle | checking | streaming | done | error | unavailable
  const [error, setError] = useState(null);
  const [speaking, setSpeaking] = useState(false);
  const abortRef = useRef(null);

  // New figures (another window, a fresh reading): show what was kept for them, if anything.
  useEffect(() => {
    const hit = cache.get(cacheKey);
    setText(hit?.text || "");
    setStats(hit?.stats || null);
    setState(hit ? "done" : "idle");
    setError(null);
  }, [cacheKey]);

  useEffect(() => () => {
    abortRef.current?.abort();
    stopSpeaking();
  }, []);

  const explain = useCallback(async () => {
    abortRef.current?.abort();
    stopSpeaking();
    setSpeaking(false);
    setError(null);
    setText("");
    setStats(null);
    setState("checking");
    try {
      const status = await api.assistantStatus(params);
      if (status.state !== "ready") {
        setError(status.hint);
        setState("unavailable");
        return;
      }
    } catch {
      setError("Can't reach the backend on port 5001. Is it running?");
      setState("error");
      return;
    }

    const controller = new AbortController();
    abortRef.current = controller;
    setState("streaming");
    let full = "";
    let done = null;
    try {
      await api.assistantChat(params, { messages: [{ role: "user", content: question }], view, range }, (e) => {
        if (e.type === "delta") {
          full += e.text;
          setText(full);
        } else if (e.type === "done") {
          done = e.stats;
          setStats(e.stats);
        } else if (e.type === "error") {
          throw new Error(e.error);
        }
      }, controller.signal);
      cache.set(cacheKey, { text: full, stats: done });
      setState("done");
    } catch (err) {
      controller.abort();
      if (err.name === "AbortError") {
        setState(full ? "done" : "idle");
      } else {
        setError(err.message);
        setState("error");
      }
    } finally {
      abortRef.current = null;
    }
  }, [params, range, view, question, cacheKey]);

  const stop = () => abortRef.current?.abort();

  const speak = () => {
    if (speaking) {
      stopSpeaking();
      setSpeaking(false);
      return;
    }
    const speaker = createSpeaker();
    speaker.push(text);
    speaker.flush();
    setSpeaking(true);
    // The browser has no "finished" callback here; a long reply is a few seconds per sentence.
    setTimeout(() => setSpeaking(false), Math.min(4000 + text.length * 70, 60000));
  };

  const busy = state === "checking" || state === "streaming";

  return (
    <div className="inset-panel p-3.5 min-w-0">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <div className="flex items-center gap-2 min-w-0">
          <span className="w-6 h-6 rounded-full border border-line bg-surface text-accent flex items-center justify-center shrink-0">
            <Sparkles className="w-3.5 h-3.5" />
          </span>
          <span className="text-sm font-semibold text-ink">Kilo's take</span>
          <span className="text-xs text-ink-muted truncate">on-device model, nothing leaves this computer</span>
        </div>
        <div className="flex items-center gap-1.5">
          {state === "done" && canSpeak && text && (
            <button onClick={speak} className={`btn-icon h-7 w-7 ${speaking ? "text-accent" : ""}`} aria-pressed={speaking}
              aria-label={speaking ? "Stop reading aloud" : "Read aloud"} title={speaking ? "Stop reading aloud" : "Read aloud"}>
              <Volume2 className="w-3.5 h-3.5" />
            </button>
          )}
          {busy ? (
            <button onClick={stop} className="btn">
              <Square className="w-3 h-3" /> Stop
            </button>
          ) : state === "idle" ? (
            <button onClick={explain} className="btn-primary">
              <Sparkles className="w-3.5 h-3.5" /> Explain in plain words
            </button>
          ) : (
            <button onClick={explain} className="btn">
              <RefreshCw className="w-3.5 h-3.5" /> {state === "done" ? "Explain again" : "Try again"}
            </button>
          )}
        </div>
      </div>

      {state === "idle" && (
        <p className="text-xs text-ink-muted mt-2 leading-relaxed">
          Kilo reads the figures on this page and tells you what they mean for you, and the one thing worth doing.
        </p>
      )}

      {(busy || text) && (
        <p className="text-sm text-ink leading-relaxed mt-2.5 whitespace-pre-wrap" aria-live="polite">
          {text ? <Figures text={text} /> : <span className="text-ink-muted">{state === "checking" ? "Waking Kilo up…" : "Reading your figures…"}</span>}
        </p>
      )}

      {error && <p className="text-sm text-neg mt-2.5 leading-relaxed">{error}</p>}

      {state === "done" && stats && (
        <p className="text-[11px] text-ink-muted tabular-nums mt-1.5">
          {stats.tokens} tokens in {stats.seconds.toFixed(1)} s on this computer
        </p>
      )}

      {onAsk && followUps.length > 0 && (state === "done" || state === "unavailable" || state === "idle") && (
        <div className="flex flex-wrap gap-1.5 mt-3">
          {followUps.map((q) => (
            <button key={q} onClick={() => onAsk(q)} className="btn rounded-full text-left">
              {q}
            </button>
          ))}
        </div>
      )}
    </div>
  );
}
