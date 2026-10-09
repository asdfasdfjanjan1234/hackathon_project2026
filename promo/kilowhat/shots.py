"""Takes the dashboard shots the Kilo What? promo shows (dark theme), into assets/shots/.

    python kilowhat/shots.py

Needs the app running (backend on :5001, frontend on :5173) with the device reader started.
Writes one PNG per card and shots.js: each shot's size, plus the figures the video quotes
(read from the same API the dashboard uses), so the numbers on screen match the screenshots.
"""
import json
import re
import urllib.request
from datetime import datetime
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "assets" / "shots"
API = "http://127.0.0.1:5001/api"
SCALE = 2   # device pixels per CSS pixel
CARD = "xpath=ancestor::*[contains(@class,'dash-card') or contains(@class,'stat-card')][1]"
ROW = "xpath=ancestor::div[contains(@class,'grid')][1]"
PANEL = "xpath=ancestor::div[contains(@class,'inset-panel')][1]"


def api(path):
    with urllib.request.urlopen(API + path, timeout=10) as r:
        return json.loads(r.read())


def card(page, text, up=CARD):
    return page.get_by_text(text, exact=True).first.locator(up)


# (file name, view, how to find it on the page)
SHOTS = [
    ("power", "Telemetry Console", lambda p: card(p, "Active power draw")),
    ("device", "This Device", lambda p: card(p, "This device", PANEL)),
    ("apps", "This Device", lambda p: card(p, "AI apps running now", PANEL)),
    ("forecast", "Billing Projection", lambda p: card(p, "Cycle projection trajectory")),
    ("decomp", "Billing Projection", lambda p: card(p, "Causal tariff decomposition")),
    ("accuracy", "Forecast Accuracy", lambda p: card(p, "Accuracy", ROW)),
    ("directives", "Load Directives", lambda p: card(p, "Load shedding & optimization directives")),
    ("carbon", "Carbon Ledger", lambda p: card(p, "Carbon budget", ROW)),
]

live, impact = api("/live"), api("/impact")
if live.get("simulated") or live.get("source") != "collector":
    raise SystemExit("The dashboard isn't showing this device's readings. Click This Device → Start reading my device.")

with sync_playwright() as p:
    OUT.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch(channel="chrome", headless=True)
    ctx = browser.new_context(viewport={"width": 1600, "height": 1000}, device_scale_factor=SCALE, color_scheme="dark")
    ctx.add_init_script("try { localStorage.setItem('watttrace-theme', 'dark') } catch (e) {}")
    page = ctx.new_page()
    page.goto("http://localhost:5173", wait_until="networkidle")
    page.wait_for_timeout(4000)
    dismiss = page.get_by_role("button", name="Dismiss")
    if dismiss.count():
        dismiss.first.click()
    page.wait_for_timeout(600)
    page.screenshot(path=str(OUT / "console.png"))   # the whole console, with Ask Kilo
    # The Ask Kilo button floats over the cards; keep it out of the card shots.
    page.add_style_tag(content="[aria-label^='Ask Kilo, your energy assistant'] { display: none !important; }")

    found = {"console": {"src": "assets/shots/console.png", "width": 1600 * SCALE, "height": 1000 * SCALE}}
    view = None
    for name, target, find in SHOTS:
        if target != view:
            page.get_by_role("button", name=target).first.click()
            page.wait_for_timeout(4000)   # charts finish animating, live readings arrive
            view = target
        el = find(page)
        el.scroll_into_view_if_needed()
        page.wait_for_timeout(300)
        box = el.bounding_box()
        el.screenshot(path=str(OUT / f"{name}.png"))
        found[name] = {"src": f"assets/shots/{name}.png", "width": round(box["width"] * SCALE),
                       "height": round(box["height"] * SCALE)}
        if name == "apps":   # the watts the video quotes are the ones in this shot
            text = el.inner_text()
            panel = {k: re.search(k + r"\s+([\d.]+)\s*W\s+(\w+)", text) for k in ("Machine", "AI apps")}
            if not panel["Machine"] or panel["Machine"].group(2) != "measured":
                raise SystemExit("The whole-machine power isn't measured right now, but the video says it is.")
    browser.close()

facts = {
    "taken": datetime.now().strftime("%Y-%m-%d %H:%M"),
    "machine_watts": float(panel["Machine"].group(1)),
    "ai_watts": float(panel["AI apps"].group(1)),
    "baseline_bill": impact["baseline_bill"],
    "current_bill": impact["current_bill"],
    "increase": impact["increase"],
    "ai_effect": impact["ai_effect"],
    "ai_share_pct": round(impact["ai_share"] * 100, 1) if impact["ai_share"] is not None else 0,
    # The AI effect is the measured local-AI kWh at the current rate (backend services/impact.py)
    "rate": round(impact["ai_effect"] / impact["local_ai_kwh"], 2) if impact["local_ai_kwh"] else None,
}
(OUT / "shots.js").write_text(f"window.SHOTS = {json.dumps(found, indent=1)};\nwindow.FACTS = {json.dumps(facts, indent=1)};\n")
print(json.dumps(facts, indent=1))
for name, shot in found.items():
    print(f"  {name:10} {shot['width']}x{shot['height']}")
