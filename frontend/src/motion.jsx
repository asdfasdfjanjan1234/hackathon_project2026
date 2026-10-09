import { useEffect, useRef, useState } from "react";

const reducedMotion = () => window.matchMedia?.("(prefers-reduced-motion: reduce)").matches;
const easeOut = (t) => 1 - Math.pow(1 - t, 3);

// A number that glides to each new value instead of jumping: counts up from 0 on first
// paint, then eases between readings. Non-numbers pass straight through.
export function useTween(value, duration = 700) {
  const target = Number.isFinite(value) ? value : null;
  const [shown, setShown] = useState(target == null || reducedMotion() ? target : 0);
  const fromRef = useRef(shown);

  useEffect(() => {
    if (target == null || reducedMotion()) {
      fromRef.current = target;
      setShown(target);
      return;
    }
    const from = fromRef.current ?? 0;
    if (from === target) return;
    const start = performance.now();
    let frame;
    const step = (now) => {
      const t = Math.min(1, (now - start) / duration);
      const v = from + (target - from) * easeOut(t);
      fromRef.current = v;
      setShown(v);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
  }, [target, duration]);

  return target == null ? value : shown;
}

// A formatted figure that counts to its value, e.g. <Counter value={bill} format={peso} />.
export function Counter({ value, format = String, duration }) {
  return format(useTween(value, duration));
}

// A key that changes each time `value` does: put it on an element to replay a one-shot
// animation (reading-flash) whenever a new reading arrives.
export function useChangeKey(value) {
  const ref = useRef({ value, n: 0 });
  if (ref.current.value !== value) ref.current = { value, n: ref.current.n + 1 };
  return ref.current.n;
}
