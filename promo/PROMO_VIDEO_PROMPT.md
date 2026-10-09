# Kilo What? — Promotional video prompt

A launch video: about 90 seconds in full, with 75 s and 60 s cuts. Part 1 is the brief for a motion designer or editor. Part 2 has one short prompt per shot for text-to-video tools (Veo, Sora, Runway, Kling), which work best on clips of 8 seconds or less. Part 3 is a single prompt for tools that take one long prompt.

On-screen figures in brackets, like **[₱X]**, come from a real recorded run. Fill them in from the dashboard before rendering. Don't invent them.

---

## Part 1 — Master brief

**Product:** Kilo What? — a power and bill monitor for AI. It runs on your own computer, reads the machine's own power sensors every 2 seconds, finds every AI app running (Claude Code, Copilot, Codex, Cursor, Ollama, LM Studio and more), and turns their watts into kilowatt-hours, pesos and CO₂. It forecasts the electricity bill, shows how much of an increase AI actually caused, and fixes it in one click by swapping a heavy local model for a lighter one.

**Goal of the video:** Answer the question everyone in the Philippines is asking, "Did AI raise my electric bill?", and show that Kilo What? gives the honest, measured answer, and the fix when it's real.

**Tagline:** *Measured, not guessed.* Closing line: *Kilo What? The honest answer about AI and your bill.*

**Audience:** Developers, students, dev shops, schools and labs running AI tools or local models; households on Meralco rates.

**Tone:** Confident, clear, a little playful (the name is a pun on "kilowatt"). Honest, never alarmist. The video should feel like a precise instrument, not a hype reel.

**Length and format:** about 90 s in full (75 s and 60 s cuts, see the end of Part 2), 16:9 at 1920×1080, 30 fps. Make a 9:16 cut for Reels/TikTok/Shorts by reframing on the dashboard cards. Burned-in captions throughout.

### Visual identity

| Element | Spec |
|---|---|
| Logo | "Kilo What?" in black brush script; the "I" is a volt-yellow lightning bolt. On dark scenes use the white version (`logo-dark.png`). |
| Palette, dark scenes ("a grid at night") | Canvas deep navy `#090D16`, surface `#0F1522`, arc blue `#38B6FF`, volt yellow `#FFD633`, green `#34D399`, warm orange `#FB923C`, red `#F87171`. |
| Palette, light scenes ("blueprint white") | Canvas `#F4F6FA`, ink `#0F1421`, electric blue `#0062E6`, volt `#CA8A04`, green `#00875A`. |
| Colour meaning | Volt yellow = live energy and current. Blue = interface and data. Green = savings and clean grid hours. Orange/red = budget warnings only. |
| Type | DM Sans throughout, sentence case, tabular figures so numbers don't jitter while counting. |
| Look | Flat, crisp, engineered. Thin 1px grid lines like a SCADA control room or a blueprint. No lens flares, no neon glow, no gradients, no stock "glowing brain". |
| UI footage | Real screen recordings of the dashboard (dark theme), slowly pushed in with 3D tilt, cards lifted out of the UI as floating layers. |

### Motion language

Every animation carries meaning, the same rules the app follows:

- **Arrival:** cards rise into place one after another (staggered, about 60 ms apart, ease-out).
- **Live load:** dashed "current flow" lines travel along wires and SVG paths; their speed follows the wattage. Faster = more power.
- **Change:** numbers count up to their value (odometer roll with tabular figures); a fresh reading gives a single soft flash on the figure.
- **Meters:** bars and the power dial "charge up" from zero and glide to new values, never snap.
- **Transitions:** wipe along a power line, or a cut on the beat of a relay click. The lightning bolt from the logo is the recurring transition device.

### Sound design

- **Music:** Minimal electronic, 110–118 BPM. Starts as a low mains hum and a pulse; a muted synth arpeggio enters at "Meet Kilo What?"; full beat with sidechained bass from 0:30; drops to near silence for the one-click switch; resolves on a warm major chord at the logo.
- **Voice-over:** Warm, clear, mid-pace, Filipino-English or neutral English; slight smile on the pun. Leave space for sound effects.
- **Signature sound:** a short electric "zap-click" (relay snapping shut plus a tiny crackle) every time the lightning bolt appears.

| Cue | Sound effect |
|---|---|
| Electric meter disc spinning | Rising mechanical whirr, ticking |
| Bill paper landing | Paper slap, register "cha-ching" detuned downward |
| Sensor scan | Soft sonar ping per part found (CPU, GPU, NPU, battery) |
| AI app icons popping in | Light bubbly "tok" per icon, pitched up each time |
| Counters rolling | Fine mechanical ticker, stops with a click |
| Current-flow lines | Low electrical hum that rises in pitch with load |
| Load spike | Transformer "thunk" and a bass swell |
| "Switch now" press | Big relay clunk, then a descending power-down whine |
| Savings / CO₂ avoided | Bright two-note chime, leaves rustle under the tree icon |
| Wall-meter match | Two beeps in unison, then a satisfying lock click |
| Logo reveal | Zap-click, brush-stroke whoosh, final chord |

---

## Part 2 — Shot list

### Scene 1 — The hook (0:00–0:10)

**Visual:** Night. A Filipino home desk, laptop open, fan turning, aircon unit on the wall. Macro shot of an analog electric meter outside, its disc spinning faster and faster. A Meralco-style bill slides into frame; the total rolls up from **₱1,500** to **₱2,500** (illustrative example, labeled as such).
**Motion graphics:** Thin volt-yellow lines trace the house wiring from meter to wall socket to laptop. A big question mark forms out of a power cable.
**On screen:** "My bill went up." → "Is it AI?"
**VO:** "Your electric bill went up. Everyone says it's AI. Is it?"
**SFX:** Meter whirr rising, paper slap, detuned cha-ching, the hum cuts out on "Is it?"

> **Generator prompt:** Cinematic macro shot at night of an analog residential electricity meter, its spinning disc accelerating, warm porch light, shallow depth of field. A thin yellow line animates along the cable from the meter into the house. Realistic, quiet, slightly tense. 6 seconds.

### Scene 2 — The problem (0:10–0:18)

**Visual:** Split screen. Left: a generic "AI cost calculator" doing token × price math, numbers scrambling. Right: the same laptop, still unknown.
**Motion graphics:** The calculator's numbers blur and stamp "ESTIMATE?" in grey. A token counter spins without ever landing.
**On screen:** "Most tools guess."
**VO:** "Most tools guess, multiplying tokens by a number from somewhere."
**SFX:** Calculator clicks, a glitchy stutter, a dull buzzer.

> **Generator prompt:** Flat motion-graphics animation on a deep navy background with a thin grid: a calculator display rapidly multiplying random numbers, digits blurring and never settling, then a grey stamp reading "estimate?". Clean, minimal, DM Sans type. 5 seconds.

### Scene 3 — Meet Kilo What? (0:18–0:25)

**Visual:** Black frame. A volt-yellow lightning bolt strikes down the middle; brush strokes paint "K LO What?" around it, the bolt becoming the "I". Push into the laptop screen as the dashboard (dark theme) boots, cards rising in one by one.
**On screen:** Logo, then "Runs on your computer. No cloud. No account. No extra hardware."
**VO:** "Meet Kilo What? It runs entirely on your own computer. No cloud, no account, no extra hardware."
**SFX:** Signature zap-click, brush whoosh, synth arpeggio enters, soft "tok" per card.

> **Generator prompt:** A single yellow lightning bolt strikes down the centre of a black frame, then black brush-script letters paint themselves around it to spell a logo, the bolt forming the letter I. Crisp, hand-painted texture, no glow. 4 seconds.

### Scene 4 — How it measures (0:25–0:40)

**Visual:** Exploded 3D view of the laptop: CPU, GPU, NPU, RAM, SSD and battery float apart. Each part gets a label tag: "measured" (green dot) or "estimated" (grey dot, marked ~). Then the "This Device" screen: detected hardware and the list of **AI apps running now**, brand icons popping in: Claude Code, GitHub Copilot, Codex, Cursor, Ollama, LM Studio, VS Code, Terminal.
**Motion graphics:**
- A sonar ring sweeps out from the chip; each component lights up as it is found.
- A clock ticks "every 2 s"; a new reading row slides into a database table each tick.
- Power from the battery splits into streams that flow into each app icon, widths proportional to watts. Overlay the attribution formula, small and elegant: *watts ≈ idle + a·CPU% + b·GPU%*.
- A small privacy badge: "Reads model names and token counts. Never prompts or code."
**On screen:** "Reads your machine's own power sensors" · "Every 2 seconds" · "Split per AI app" · "Estimates always labeled"
**VO:** "Every two seconds it reads your computer's own power sensors, on Windows, Mac or Linux, and finds every AI app running. The total is measured, not guessed. Then it splits that power between your apps by how much CPU and GPU each one uses."
**SFX:** Sonar pings per part, bubbly "tok" per icon, steady 2-second tick, fine ticker on the formula.

> **Generator prompt:** Exploded isometric view of a thin laptop on a deep navy blueprint grid, internal components (processor, graphics chip, memory, SSD, battery) floating apart and labeled with small white tags. A thin circular scan ring expands from the processor and each part lights up in electric blue as it passes. Clean technical illustration, flat colours, no glow. 6 seconds.

### Scene 5 — The honest answer, then the real cost (0:40–0:52)

**Visual:** The Live Wattage dial on the Telemetry Console. With only cloud tools open (Claude Code, Copilot) the AI share sits at a fraction of a watt. Caption: "Cloud AI: runs in the provider's data center. Not on your bill." Then a terminal starts a local model (Ollama, `llama3.1:8b`): the dial charges up to **[X W]**, current-flow dashes speed up across the power path.
Cut to the **If You Kept This Up** card: "4 hours a day = **[₱X]** a month." The machines stepper clicks from 1 to 10: the figure multiplies for a dev shop.
**Motion graphics:** Dial needle sweeps with spring physics; the AI slice of a power split bar grows in volt yellow; the peso figure rolls like an odometer; ten laptop silhouettes appear in a row.
**On screen:** "Cloud AI: a fraction of a watt." → "Local AI: real money."
**VO:** "Using cloud AI? Honestly, it didn't raise your bill. But run a model on your own machine, and it's real money. Every day. On every machine."
**SFX:** Hum rising in pitch with the dial, transformer thunk at the spike, ticker on the pesos, ten quick "tok"s for the laptops.

> **Generator prompt:** Close-up of a minimalist circular power gauge on a dark navy dashboard, the needle sweeping from near zero up to a high reading with a slight spring overshoot, small dashes flowing faster along a thin line beside it. Electric blue and yellow on navy, DM Sans numerals counting up. 5 seconds.

### Scene 6 — Forecast and verdict (0:52–1:00)

**Visual:** **Billing Projection** view. The forecast line draws itself to the end of the billing cycle, with a shaded band; a "with recommendations" line peels off lower in green. The bill increase breaks into three blocks: rate change, AI, everything else; the AI block lights volt yellow with "AI explains **[X]%**". A brief overlay of the **Forecast Accuracy** card: precision, recall and F1 bars charging up.
**Motion graphics:** Grid of 15-minute steps ticking forward; a small map of Luzon pulses once with the caption "Pre-trained on Luzon grid demand, fine-tuned on your device."
**VO:** "It forecasts your bill, trained on the Luzon grid and fine-tuned on your own usage, and shows exactly how much of the increase is AI."
**SFX:** Pen-scratch line draw, three block "thunks", soft chime on the accuracy bars.

> **Generator prompt:** Animated line chart on a dark navy grid: a blue line draws itself left to right to a dashed vertical "end of cycle" marker, a second green line branches off and ends lower. A horizontal bar then splits into three labeled segments, the middle one highlighted yellow. Flat, minimal, precise. 6 seconds.

### Scene 7 — The fix, in one click (1:00–1:08)

**Visual:** **Load Directives**: cards labeled STOP, SWITCH, REDUCE, each with its saving in pesos and grams of CO₂. Cursor clicks **Switch now** on the big model. Cut to the live dial: **[X W] → [Y W]**, the "before → now" line appears on the card.
**Motion graphics:** The heavy model's icon shrinks and slides out; the lighter model slides in. Current-flow dashes visibly slow down. A green "−[Y] W" badge lands.
**On screen:** "It doesn't just tell you. It fixes it."
**VO:** "And it doesn't just tell you. It fixes it. One click: heavy model out, lighter model in."
**SFX:** Music drops out. Big relay clunk on the click, descending power-down whine, then the beat returns.

### Scene 8 — When to run it (1:08–1:15)

**Visual:** **Carbon Ledger → Cleanest Hours**: a 24-hour bar chart of Luzon grid CO₂ intensity with the cleanest window marked in green, and the device's AI hours sliding under it. Then **Best Time**: Meralco Peak/Off-Peak tiles showing the cheaper night hours. Carbon equivalents pop up as small icons: car km, phone charges, trees.
**On screen:** "Cleanest hours on the grid" · "Cheapest hours on your tariff" · "CO₂ avoided: **[X] g/month**"
**VO:** "It tells you when the grid is cleanest and power is cheapest, so heavy jobs run then."
**SFX:** Day-to-night ambient shift (birds → crickets), leaf rustle and two-note chime on CO₂ avoided.

### Scene 9 — Kilo, and proof (1:15–1:22)

**Visual:** The **Kilo** assistant panel. A user asks by voice, "Is AI why my bill went up?"; the answer streams in, citing dashboard figures. Badge: "Runs locally on Ollama." Then **This Device → Wall-Meter Check**: a plug-in power meter's display next to the app's reading, two numbers converging; "Within **[X]%** of a wall meter."
**VO:** "Ask Kilo anything, privately, on your machine. And check every number against a meter at the wall."
**SFX:** Mic-open blip, soft typing ticks as the reply streams, two beeps in unison, lock click.

### Scene 10 — Close (1:22–1:30)

**Visual:** Pull back from the laptop to the dark room, then out through the window to a city grid at night: streetlights and power lines, with volt-yellow current flowing calmly. Lightning bolt strikes; logo paints on; tagline fades up beneath.
**On screen:** **Kilo What?** · "Measured, not guessed." · "The honest answer about AI and your bill."
**VO:** "Kilo What? Measured, not guessed. The honest answer about AI and your bill."
**SFX:** Zap-click, brush whoosh, final warm chord, mains hum fades to silence.

> **Generator prompt:** Slow aerial pull-back at night over a Philippine city, streetlights and overhead power lines; thin yellow light pulses travel calmly along the lines. Camera rises until the city becomes a grid of lights on deep navy. Cinematic, quiet, no lens flare. 8 seconds.

*Running time with all scenes is about 90 s. To hit 75 s or a 60 s cut, drop Scene 2 first, then Scene 8. Keep Scenes 4, 5 and 7: they are the product.*

---

## Part 3 — One-prompt version

> Create a 75-second promotional video for **Kilo What?**, a desktop app that measures how much electricity AI uses on your own computer and what it does to your electric bill and carbon footprint. Goal: answer "Did AI raise my electric bill?" with a measured, honest answer, and show the one-click fix. Setting: a Filipino home at night; prices in pesos, Meralco bill, Luzon grid. Style: crisp flat motion graphics on a deep navy blueprint grid (#090D16) with electric blue (#38B6FF) for data, volt yellow (#FFD633) for live energy, green (#34D399) for savings; DM Sans type, sentence case; no glows, gradients or lens flares. Logo: black brush script "Kilo What?" where the "I" is a yellow lightning bolt. Structure: (1) electric meter spinning faster, bill total rolling up, "Is it AI?"; (2) other tools just guess, calculator numbers blurring; (3) lightning bolt strikes and the logo paints on, the dashboard boots with cards rising one by one; (4) exploded laptop view, components scanned and labeled measured or estimated, readings every 2 seconds, AI app icons pop in (Claude Code, Copilot, Codex, Cursor, Ollama) and power streams split between them; (5) a live power dial: cloud AI stays near zero watts, then a local model starts and the dial climbs, a monthly peso cost rolls up and multiplies across 10 machines; (6) a bill forecast line draws to the end of the cycle and the increase splits into rate change, AI and other; (7) a "Switch now" click, heavy model swapped for a lighter one, the dial drops and flowing current slows; (8) a 24-hour grid chart highlights the cleanest and cheapest hours, CO₂ avoided shown as trees and phone charges; (9) a local AI assistant named Kilo answers a spoken question, and the app's reading matches a plug-in wall meter; (10) pull back to a city power grid at night, logo and tagline "Measured, not guessed." Motion: staggered card arrivals, counters that roll up to their value, dashed current flowing along lines at a speed that follows the load, meters that charge up and glide. Sound: minimal electronic score at 115 BPM that starts as a mains hum, drops to silence for the switch, and resolves on a warm chord; sound effects for meter whirr, sonar pings on each sensor, bubbly pops for app icons, mechanical number tickers, a relay clunk and power-down whine on the switch, a chime and leaf rustle for CO₂ saved, and an electric zap-click whenever the lightning bolt appears. Warm, confident voice-over with burned-in captions.
