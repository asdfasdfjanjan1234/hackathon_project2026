/**
 * Voice for the assistant, from the browser's Web Speech API.
 *
 * Speaking uses the system's voices, on this computer. Listening uses the browser's speech
 * recognition: Safari can do it on the device, Chrome sends the audio to Google. Firefox has
 * no recognition, so the mic button is hidden there.
 */

const Recognition = typeof window !== "undefined" && (window.SpeechRecognition || window.webkitSpeechRecognition);
const synth = typeof window !== "undefined" ? window.speechSynthesis : null;

export const canListen = Boolean(Recognition);
export const canSpeak = Boolean(synth);

/**
 * Listens for one question. onText(text, isFinal) gets the words as they're recognised;
 * onEnd runs when listening stops. Returns a function that stops listening.
 */
export function listen({ onText, onEnd, onError, lang = navigator.language || "en-US" }) {
  const r = new Recognition();
  r.lang = lang;
  r.interimResults = true;
  r.continuous = false;
  r.onresult = (e) => {
    const results = Array.from(e.results);
    onText(results.map((res) => res[0].transcript).join(""), results.every((res) => res.isFinal));
  };
  r.onerror = (e) => onError?.(e.error);
  r.onend = () => onEnd?.();
  r.start();
  return () => r.stop();
}

// Units and symbols read out as words ("₱12.50" → "12.50 pesos", "CO₂" → "C O 2").
export const forSpeech = (text) =>
  text
    .replace(/₱\s?([\d,]+(?:\.\d+)?)/g, "$1 pesos")
    .replace(/CO₂/g, "C O 2")
    .replace(/(\d)\s?kWh\b/g, "$1 kilowatt hours")
    .replace(/(\d)\s?Wh\b/g, "$1 watt hours")
    .replace(/(\d)\s?kg\b/g, "$1 kilograms")
    .replace(/(\d)\s?W\b/g, "$1 watts")
    .replace(/(\d)\s?g\b/g, "$1 grams")
    .replace(/\s·\s/g, ", ");

// A sentence is done at . ! or ? followed by a space (not "1,500.72").
const SENTENCE_END = /[.!?]["')\]]?\s/g;

/**
 * Speaks a reply while it's still being written: push() each new piece, and every finished
 * sentence is read out straight away. flush() reads what's left; cancel() stops talking.
 */
export function createSpeaker() {
  let pending = "";
  let stopped = false;
  const say = (text) => {
    const words = forSpeech(text).trim();
    if (!words || stopped || !synth) return;
    const u = new SpeechSynthesisUtterance(words);
    u.rate = 1.05;
    synth.speak(u);
  };
  return {
    push(piece) {
      pending += piece;
      let last = -1;
      for (const m of pending.matchAll(SENTENCE_END)) last = m.index + m[0].length;
      if (last > 0) {
        say(pending.slice(0, last));
        pending = pending.slice(last);
      }
    },
    flush() {
      say(pending);
      pending = "";
    },
    cancel() {
      stopped = true;
      pending = "";
      synth?.cancel();
    },
  };
}

export const stopSpeaking = () => synth?.cancel();
