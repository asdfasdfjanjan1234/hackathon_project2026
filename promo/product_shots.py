"""Takes the dashboard screenshots the promo video shows (dark theme), into assets/shots/.

    python product_shots.py

Needs the app running (backend on :5001, frontend on :5173) with the device reader started.
Writes the screenshots and shots.js, which tells video.html where each cut-out is and what
the machine was drawing, so the numbers in the video are the ones in the screenshots.
"""
import json
import re
from pathlib import Path

from playwright.sync_api import sync_playwright

OUT = Path(__file__).resolve().parent / "assets" / "shots"
SCALE = 2   # device pixels per CSS pixel
PAD = 8     # CSS pixels kept around a cut-out


def rect(left, top, right, bottom):
    """A cut-out in image pixels, from CSS-pixel edges."""
    return {"x": round((left - PAD) * SCALE), "y": round((top - PAD) * SCALE),
            "w": round((right - left + 2 * PAD) * SCALE), "h": round((bottom - top + 2 * PAD) * SCALE)}


def of(locator):
    box = locator.bounding_box()
    return box["x"], box["y"], box["x"] + box["width"], box["y"] + box["height"]


def console(page):
    card = page.get_by_text("Active power draw", exact=True).first.locator(
        "xpath=ancestor::div[contains(@class,'stat-card') or contains(@class,'dash-card')][1]")
    return {"rects": {"active_power_card": rect(*of(card))}}


def device(page):
    panel = page.locator("h3", has_text="AI apps running now").locator("xpath=../..")
    machine = panel.get_by_text("Machine", exact=True).locator("xpath=..")
    ai_apps = panel.get_by_text("AI apps", exact=True).locator("xpath=..")
    reading = re.search(r"([\d.]+)\s*W\s*(\w+)", machine.inner_text())
    if not reading or reading.group(2) != "measured":
        raise SystemExit("The whole-machine power isn't measured on this computer right now, "
                         "but the video says it is. Start the device reader on a laptop on battery.")

    # The AI app drawing the most right now, down to its CPU / GPU / RAM line.
    rows = panel.locator("div.mt-3 > div.flex")
    watts = [float((re.findall(r"([\d.]+) W", rows.nth(i).inner_text()) or ["0"])[-1]) for i in range(rows.count())]
    top = rows.nth(watts.index(max(watts)))
    left, y0, right, _ = of(top)
    legend_bottom = of(top.locator("div.flex-wrap").first)[3]

    readings = page.get_by_text("Power readings", exact=True).locator("xpath=..")
    rx0, ry0, rx1, ry1 = of(readings)
    return {
        "machine_watts": float(reading.group(1)),
        "rects": {
            "machine_rows": rect(of(machine)[0], of(machine)[1], of(ai_apps)[2], of(ai_apps)[3]),
            "top_app": rect(left, y0, right, legend_bottom),
            "power_readings": rect(rx0, ry0 + 6, rx1, ry1),   # below the divider line above it
        },
    }


SHOTS = [("console", "Telemetry Console", 1600, 900, console), ("device", "This Device", 1440, 1500, device)]

with sync_playwright() as p:
    OUT.mkdir(parents=True, exist_ok=True)
    browser = p.chromium.launch(channel="chrome", headless=True)
    found = {}
    for name, view, width, height, measure in SHOTS:
        ctx = browser.new_context(viewport={"width": width, "height": height}, device_scale_factor=SCALE, color_scheme="dark")
        ctx.add_init_script("try { localStorage.setItem('watttrace-theme', 'dark') } catch (e) {}")
        page = ctx.new_page()
        page.goto("http://localhost:5173", wait_until="networkidle")
        page.get_by_role("button", name=view).first.click()
        page.wait_for_timeout(4000)  # charts finish animating, live readings arrive
        found[name] = {"src": f"assets/shots/{name}.png", "width": width * SCALE, "height": height * SCALE, **measure(page)}
        page.screenshot(path=str(OUT / f"{name}.png"))
        ctx.close()
    browser.close()
    (OUT / "shots.js").write_text(f"window.SHOTS = {json.dumps(found, indent=1)};\n")
    print(json.dumps(found, indent=1))
