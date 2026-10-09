"""Keeps a local model busy for the live demo, standing in for someone using it.

    python demo_load.py --model llama3:70b
    python demo_load.py --model llama3.2:3b --pause 1

Sends coding prompts to Ollama one after another. Before each prompt it asks the backend
which model to use (GET /api/actions/state): after "Apply" on a SWITCH recommendation in
the dashboard, it moves to the smaller model, so the live watts drop on screen.
Stop with Ctrl+C.
"""

import argparse
import itertools
import json
import time
import urllib.request

from app.services.local_models import ollama_url

PROMPTS = [
    "Write a Python function that checks whether a string is a palindrome, with tests.",
    "Explain the difference between a process and a thread in three short paragraphs.",
    "Write a SQL query for the top 5 customers by total order value, then explain it.",
    "Refactor this into a list comprehension: out = []\nfor x in xs:\n    if x % 2:\n        out.append(x * x)",
    "Write a React component for a counter with increment and reset buttons.",
]


def _json(url, body=None, timeout=10):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as res:
        return json.load(res)


def current_model(start, backend):
    try:
        switches = _json(f"{backend}/api/actions/state", timeout=2).get("switches") or {}
    except (OSError, ValueError):
        return start  # backend not running: keep the model we started with
    model, seen = start, {start}
    while switches.get(model) and switches[model] not in seen:  # follow chained switches
        model = switches[model]
        seen.add(model)
    return model


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--model", required=True, help="Ollama model to start with, e.g. llama3:70b")
    parser.add_argument("--backend", default="http://127.0.0.1:5001", help="dashboard backend URL")
    parser.add_argument("--tokens", type=int, default=400, help="max tokens per answer")
    parser.add_argument("--pause", type=float, default=0.0, help="seconds between prompts")
    args = parser.parse_args()

    print(f"Sending prompts to Ollama at {ollama_url()}. Ctrl+C to stop.")
    last = None
    try:
        for prompt in itertools.cycle(PROMPTS):
            model = current_model(args.model, args.backend)
            if model != last:
                print(f"\n→ using {model}" + (f" (switched from {last})" if last else ""))
                last = model
            t0 = time.time()
            try:
                res = _json(f"{ollama_url()}/api/generate", {
                    "model": model, "prompt": prompt, "stream": False,
                    "options": {"num_predict": args.tokens}}, timeout=600)
            except OSError as e:
                print(f"  Ollama error: {e}; retrying in 5 s")
                time.sleep(5)
                continue
            tokens = res.get("eval_count") or 0
            seconds = (res.get("eval_duration") or 0) / 1e9 or (time.time() - t0)
            print(f"  {tokens} tokens in {time.time() - t0:.1f} s ({tokens / seconds:.1f} tok/s)")
            time.sleep(args.pause)
    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
