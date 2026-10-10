"""Takes what the "how it works" video shows from the running app, into assets/shots/.

    python howitworks/shots.py

Needs the app running (backend on :5001, frontend on :5173) with the device reader started, and
Ollama running with the assistant's model downloaded. While it works, it keeps that model busy
(as backend/demo_load.py does), so the readings show a local model next to the cloud apps.

Writes the screenshots, and shots.js: where things are in them, the figures the video quotes
(from the same API responses the screenshots were drawn from) and Kilo's reply to one question,
word for word. The video quotes nothing else. The bill and forecast figures count whatever
history the app holds: for measured ones only, run backend/seed_history.py --remove first.
The watts are whatever the machine draws at the time: on battery in Low Power Mode this MacBook
Air drew about half of what it did plugged in (13 W against 26 W with the model busy).

The bill moves by a centavo every few minutes as readings come in, so Kilo is asked and the
screens are frozen within seconds of each other, and it starts over if they still disagree.
"""
import json
import re
import threading
import time
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import Error as PlaywrightError, sync_playwright

OUT = Path(__file__).resolve().parent / "assets" / "shots"
APP = "http://localhost:5173"
API = "http://127.0.0.1:5001/api"
OLLAMA = "http://127.0.0.1:11434"
SCALE = 2            # device pixels per CSS pixel
VIEW = (1600, 1000)  # the window the video shows
MAIN_HEIGHT = 1800   # how far down the console the video scrolls
QUESTION = "How much is AI adding to my bill?"
TRIES = 5
FACTS_TTL_S = 62     # the backend gives Kilo the same facts for a minute (routes/assistant.py)
CARD = "xpath=ancestor::*[contains(@class,'dash-card') or contains(@class,'stat-card')][1]"
ASK_KILO = "[aria-label^='Ask Kilo, your energy assistant']"

# Prompts for the model kept busy during the shots (backend/demo_load.py's)
PROMPTS = [
    "Write a Python function that checks whether a string is a palindrome, with tests.",
    "Explain the difference between a process and a thread in three short paragraphs.",
    "Write a SQL query for the top 5 customers by total order value, then explain it.",
]


def get(url, timeout=20):
    with urllib.request.urlopen(url, timeout=timeout) as r:
        return json.loads(r.read())


def post(url, body, timeout=300):
    req = urllib.request.Request(url, data=json.dumps(body).encode(), headers={"Content-Type": "application/json"})
    return urllib.request.urlopen(req, timeout=timeout)


def peso(x):
    """As the backend writes pesos for Kilo (services/assistant.py)."""
    if 0 < abs(x) < 0.01:
        return "under ₱0.01"
    return f"₱{x:,.0f}" if abs(x) >= 10 and float(x).is_integer() else f"₱{x:,.2f}"


def local_working(live):
    return [a for a in live.get("apps", []) if a.get("kind") == "local" and a.get("activity") == "working"]


def under_load(live):
    """A local model is working, and the whole-machine sensor has caught up with it (the battery
    controller averages over some seconds)."""
    working = local_working(live)
    return bool(working) and working[0]["watts"] >= 4 and not live.get("estimated") and live["watts"] >= live["ai_watts"] + 4


class Busy(threading.Thread):
    """Keeps the model generating until stopped."""

    def __init__(self, model):
        super().__init__(daemon=True)
        self.model, self.stopped = model, threading.Event()

    def run(self):
        i = 0
        while not self.stopped.is_set():
            try:
                post(f"{OLLAMA}/api/generate", {"model": self.model, "prompt": PROMPTS[i % len(PROMPTS)], "stream": False,
                                                 "options": {"num_predict": 250}}).read()
            except OSError as e:
                print("  Ollama:", e)
                self.stopped.wait(3)
            i += 1

    def stop(self):
        self.stopped.set()
        self.join(timeout=120)


def bill_data(forecast):
    """What Kilo is given about the bill (services/assistant.py, _bill): the lines the video shows,
    and every peso figure a reply may quote."""
    over = forecast["forecast_bill"] - forecast["budget"]
    costly = [m for m in forecast["by_model"] if m["monthly_cost"] > 0][:5]
    lines = [f"Forecast bill for this cycle: {peso(forecast['forecast_bill'])}",
             f"{peso(forecast['baseline_bill'])} household bill before AI + {peso(forecast['ai_cost'])} from AI on this computer",
             f"Against the {peso(forecast['budget'])} budget: " + (f"OVER by {peso(over)}" if over > 0 else f"under by {peso(-over)}"),
             "Biggest: " + ", ".join(f"{m['model'].split(' · ')[0]} {peso(m['monthly_cost'])}" for m in costly[:2])]
    allowed = {peso(v) for v in (forecast["forecast_bill"], forecast["baseline_bill"], forecast["ai_cost"], forecast["budget"],
                                 abs(over), forecast["forecast_bill_with_recommendations"], forecast.get("monthly_savings") or 0)}
    return lines, allowed | {peso(m["monthly_cost"]) for m in costly}


def ask_kilo(allowed):
    """Kilo's reply to QUESTION through the app's own API, with how it streamed and the live watts
    while it answered. `wrong` lists any peso figure the app didn't give it."""
    watts, done = [], threading.Event()

    def poll():
        while not done.is_set():
            try:
                watts.append(max((a["watts"] for a in local_working(get(API + "/live", timeout=5))), default=0.0))
            except OSError:
                pass
            done.wait(1.0)

    threading.Thread(target=poll, daemon=True).start()
    t0, pieces, stats = time.time(), [], None
    with post(API + "/assistant/chat", {"messages": [{"role": "user", "content": QUESTION}],
                                        "view": "dashboard", "range": "30d"}) as res:
        for line in res:
            event = json.loads(line)
            if event["type"] == "delta":
                pieces.append([round(time.time() - t0, 3), event["text"]])
            elif event["type"] == "done":
                stats = event["stats"]
            else:
                raise SystemExit(f"Kilo didn't answer: {event}")
    done.set()
    reply = "".join(text for _, text in pieces).strip()
    figures = [f.rstrip(".,") for f in re.findall(r"₱[\d,]+(?:\.\d+)?", reply)]
    return {"question": QUESTION, "reply": reply, "pieces": pieces, "figures": figures,
            "wrong": [f for f in figures if f not in allowed],
            "first_word_s": stats["first_word_seconds"], "tokens": stats["tokens"],
            "tokens_per_second": stats["tokens_per_second"], "model": stats["model"],
            "watts_while_answering": round(max(watts, default=0.0), 1)}


def box(el, origin=(0, 0)):
    b = el.bounding_box()
    return {"x": round(b["x"] - origin[0], 1), "y": round(b["y"] - origin[1], 1), "w": round(b["width"], 1), "h": round(b["height"], 1)}


def card(page, text, up=CARD):
    return page.get_by_text(text, exact=True).first.locator(up)


def hide_ask(page, hidden):
    """The Ask Kilo button floats over the cards; the video draws it separately."""
    page.evaluate("""([sel, hidden]) => {
        document.getElementById('promo-hide')?.remove();
        if (!hidden) return;
        const style = document.createElement('style');
        style.id = 'promo-hide';
        style.textContent = sel + ' { visibility: hidden !important; }';
        document.head.appendChild(style);
    }""", [ASK_KILO, hidden])


def go(page, view):
    page.evaluate("v => { location.hash = v }", view)
    page.wait_for_timeout(4000)   # cards rise in, charts finish drawing


class Frozen:
    """A page whose every API request gets the first answer that request got, so the dark and the
    light shots, and the figures taken from them, all show the same reading."""

    def __init__(self, browser):
        self.seen = {}
        ctx = browser.new_context(viewport={"width": VIEW[0], "height": VIEW[1]}, device_scale_factor=SCALE, color_scheme="dark")
        ctx.add_init_script("try { localStorage.setItem('watttrace-theme', 'dark') } catch (e) {}")
        self.ctx, self.page = ctx, ctx.new_page()
        self.page.on("pageerror", lambda e: print("  page error:", e))
        self.page.route(re.compile(r"^http://localhost:5173/api/"), self._route)
        self.page.goto(APP + "/#dashboard", wait_until="load")
        for _ in range(120):   # until the dashboard has asked for its figures
            if all(any(u.split("?")[0].endswith("/api/" + path) for u in self.seen) for path in ("live", "forecast", "impact", "carbon")):
                break
            self.page.wait_for_timeout(250)

    def _route(self, route):
        req = route.request
        if req.method != "GET":
            return route.abort()   # Kilo's own briefing would compete with the busy model
        if req.url not in self.seen:
            try:
                res = route.fetch()
            except PlaywrightError:   # the page closed with a request on its way
                return
            headers = {k: v for k, v in res.headers.items() if k.lower() not in ("content-encoding", "content-length")}
            self.seen[req.url] = (res.status, headers, res.body())
        status, headers, body = self.seen[req.url]
        route.fulfill(status=status, headers=headers, body=body)

    def answer(self, path):
        """The frozen response to /api/<path>, whatever its query."""
        for url, (_, _, body) in self.seen.items():
            if url.split("?")[0].endswith("/api/" + path):
                return json.loads(body)
        raise SystemExit(f"The dashboard never asked for /api/{path}")

    def close(self):
        self.page.unroute_all(behavior="wait")   # lets the requests on their way finish first
        self.ctx.close()


def main():
    live = get(API + "/live")
    if live.get("simulated") or live.get("source") != "collector":
        raise SystemExit("The dashboard isn't showing this device's readings. Click This Device → Start reading my device.")
    kilo = get(API + "/assistant/status")
    if kilo["state"] != "ready":
        raise SystemExit(f"Kilo can't answer: {kilo['hint']}")

    OUT.mkdir(parents=True, exist_ok=True)
    busy = Busy(kilo["model"])
    busy.start()
    print("Keeping", kilo["model"], "busy until the readings show it…")
    for _ in range(90):
        if under_load(get(API + "/live")):
            break
        time.sleep(2)
    else:
        raise SystemExit("The readings never showed the local model working. Is the device reader on?")

    shots, where = {}, {}

    def shoot(name, el=None, page=None):
        (el or page).screenshot(path=str(OUT / f"{name}.png"))
        size = el.bounding_box() if el else page.viewport_size
        shots[name] = {"src": f"assets/shots/{name}.png", "w": round(size["width"], 1), "h": round(size["height"], 1)}
        print(f"  {name:14} {shots[name]['w']:.0f} x {shots[name]['h']:.0f}")

    with sync_playwright() as p:
        browser = p.chromium.launch(channel="chrome", headless=True)

        # Kilo's answer, then at once the screens, until both show the same bill.
        asked = 0
        for attempt in range(1, TRIES + 1):
            time.sleep(max(0, asked + FACTS_TTL_S - time.time()))
            busy.stop()
            data, allowed = bill_data(get(API + "/forecast"))
            asked = time.time()
            reply = ask_kilo(allowed)
            busy = Busy(kilo["model"])
            busy.start()
            print(f"Kilo ({attempt}):", reply["reply"])
            if reply["wrong"]:
                print("  quotes figures the app didn't give it:", reply["wrong"])
                continue
            for _ in range(12):   # the reader's next reading, with the model busy again
                if under_load(get(API + "/live")):
                    break
                time.sleep(1)
            frozen = Frozen(browser)
            same, loaded = bill_data(frozen.answer("forecast"))[0] == data, under_load(frozen.answer("live"))
            if same and loaded:
                break
            print("  again:", "the reading caught the model between prompts" if same else "the bill moved by a centavo")
            frozen.close()
        else:
            raise SystemExit("Couldn't get Kilo and the screens to show the same bill. Run it again.")
        reply["data"] = data

        page = frozen.page
        page.wait_for_timeout(5000)
        readings = get(API + "/readings?limit=8")["readings"]   # the readings around the frozen one
        dismiss = page.get_by_role("button", name="Dismiss")
        if dismiss.count():
            dismiss.first.click()
            page.wait_for_timeout(500)

        # The console in both themes: the window (sidebar and top bar), the Ask Kilo button that
        # floats over it, and the page inside it, which the video scrolls.
        for theme in ("dark", "light"):
            page.set_viewport_size({"width": VIEW[0], "height": VIEW[1]})
            page.get_by_role("button", name=f"{theme.capitalize()} theme").click()
            page.mouse.move(800, 600)   # off the button, so it isn't drawn hovered
            page.wait_for_timeout(900)
            main_el = page.locator("main").first
            if theme == "dark":
                where["main"] = box(main_el)
                where["toggle"] = {t: box(page.get_by_role("button", name=f"{t.capitalize()} theme")) for t in ("light", "dark")}
                where["ask"] = box(page.locator(ASK_KILO).first)
            shoot(f"ask-{theme}", el=page.locator(ASK_KILO).first)
            hide_ask(page, True)
            shoot(f"window-{theme}", page=page)
            page.set_viewport_size({"width": VIEW[0], "height": round(where["main"]["y"]) + MAIN_HEIGHT})
            page.wait_for_timeout(1200)
            if theme == "dark":
                top = main_el.bounding_box()
                origin = (top["x"], top["y"])
                where["stats"] = {key: box(card(page, text), origin) for key, text in (
                    ("watts", "Active power draw"), ("energy", "AI energy on bill (30D)"),
                    ("cost", "AI cost this cycle"), ("bill", "Cycle projection"))}
                where["apps"] = box(card(page, "AI apps right now"), origin)
                where["draw"] = box(page.get_by_text("The whole machine, read every 2 s").first.locator(CARD), origin)
            shoot(f"main-{theme}", el=main_el)
            hide_ask(page, False)

        page.set_viewport_size({"width": VIEW[0], "height": 1400})
        page.get_by_role("button", name="Dark theme").click()
        hide_ask(page, True)
        for name, view, find in (
            ("verdict", "analytics", lambda: card(page, "Did AI raise my bill?")),
            ("recs", "recommendations", lambda: card(page, "What to change")),
        ):
            go(page, view)
            el = find()
            el.scroll_into_view_if_needed()
            page.wait_for_timeout(400)
            shoot(name, el=el)
            corner = el.bounding_box()
            origin = (corner["x"], corner["y"])
            if name == "verdict":   # the video shows the card down to here
                where["verdict"] = {"cut": box(el.get_by_text("What that energy equals", exact=True).first, origin)["y"]}
            if name == "recs":      # what the video points at
                apply = el.get_by_role("button", name=re.compile(r"^(Unload|Switch) now$"))
                where["recs"] = {
                    "savings": box(el.get_by_text("Possible savings", exact=True).first.locator("xpath=.."), origin),
                    "saves": [box(s.locator("xpath=.."), origin) for s in el.get_by_text("Saves", exact=True).all()],
                    "apply": box(apply.first, origin) if apply.count() else None,
                }
        frozen.close()
        browser.close()

    busy.stop()
    live, impact, forecast = frozen.answer("live"), frozen.answer("impact"), frozen.answer("forecast")
    system, recs = frozen.answer("system"), frozen.answer("recommendations")
    status = get(API + "/device/status")
    accuracy = get(API + "/forecast/accuracy")

    default = next(t for t in accuracy["thresholds"] if t["used_wh"] == accuracy["default_used_wh"]) if accuracy.get("available") else None
    arima = (forecast.get("method") or {}).get("arima") or {}
    facts = {
        "taken": datetime.now().strftime("%Y-%m-%d %H:%M"),
        "device": system["system"]["device"]["model"], "cpu": system["system"]["cpu"], "os": system["system"]["os"],
        "sensors": system["sensors"],
        "power_model": status.get("power_model"),
        "live": {"watts": live["watts"], "ai_watts": live["ai_watts"], "cpu_percent": live["cpu_percent"], "gpu_percent": live["gpu_percent"],
                 "components": live["components"],
                 "apps": [{"name": a["name"], "kind": a["kind"], "activity": a.get("activity"), "watts": a["watts"]} for a in live["apps"]]},
        "readings": [{"ts": r["ts"], "watts": r.get("measured_watts") or r.get("est_watts"), "measured": r.get("measured_watts") is not None,
                      "cpu": r["cpu_percent"], "gpu": r["gpu_percent"], "ai": round(sum(a["watts"] for a in r["apps"]), 2)} for r in readings],
        "bill": {k: impact[k] for k in ("baseline_bill", "current_bill", "increase", "ai_effect", "other_effect", "rate_effect", "local_ai_kwh")},
        "ai_share_pct": round(impact["ai_share"] * 100, 1),
        "forecast": {"bill": forecast["forecast_bill"], "baseline": forecast["baseline_bill"], "ai_cost": forecast["ai_cost"],
                     "range": forecast["forecast_range"], "budget": forecast["budget"], "cycle": forecast["cycle"],
                     "days_left": forecast["days_left"], "method": forecast["method"]["name"], "interval": forecast["method"].get("interval"),
                     "beats_baselines": arima.get("beats_baselines"), "models": arima.get("models"),
                     "daily": [{"date": d["date"], "ai_cost": d["ai_cost"], "past": d["is_past"], "today": d["is_today"]} for d in forecast["daily"]]},
        "accuracy": default and {k: default["chosen"][k] for k in ("accuracy", "precision", "recall", "f1", "steps")},
        "accuracy_step_minutes": (accuracy.get("data") or {}).get("step_minutes"),
        "savings": {"pesos": recs["monthly_savings"], "co2_kg": recs["monthly_co2_saved_kg"], "count": len(recs["recommendations"])},
        "kilo": reply,
    }
    (OUT / "shots.js").write_text(f"window.SHOTS = {json.dumps(shots, indent=1)};\nwindow.WHERE = {json.dumps(where, indent=1)};\n"
                                  f"window.FACTS = {json.dumps(facts, indent=1, ensure_ascii=False)};\n")
    print(json.dumps({k: v for k, v in facts.items() if k not in ("forecast", "readings", "kilo")}, indent=1, ensure_ascii=False))


if __name__ == "__main__":
    main()
