"""Builds a 60-second promo video from a cut's narration.json and video.html.

    python build.py [--cut=NAME] voice     voice-over clips, out/timeline.js (when each line is spoken) and the .srt captions
    python build.py [--cut=NAME] music     out/music.wav, synthesized
    python build.py [--cut=NAME] sfx       out/sfx.wav, the sound effects the page asks for (cuts with a sound.py)
    python build.py [--cut=NAME] still 12.5 [more times]   out/stills/*.png, to check a moment of the video
    python build.py [--cut=NAME] frames    out/silent.mp4, every frame of video.html
    python build.py [--cut=NAME] mux       the finished .mp4: voice over the music and sound effects
    python build.py [--cut=NAME] all       everything, in order

Cuts (default kilowhat):
    kilowhat    KiloWhat-promo.mp4, from kilowhat/ (narration.json, video.html, sound.py, shots.py)
    howitworks  KiloWhat-how-it-works.mp4, from howitworks/: how the app reads, forecasts and explains
    watttrace   WattTrace-promo.mp4, the first release, from this folder

Everything runs on this computer. Needs:
    pip install kokoro-onnx soundfile numpy imageio-ffmpeg playwright
    Google Chrome installed (used headless to draw the frames)
    KOKORO_DIR=<folder holding kokoro-v1.0.onnx and voices-v1.0.bin>
        from https://github.com/thewh1teagle/kokoro-onnx/releases/tag/model-files-v1.0
        Without it, the voice falls back to the macOS `say` command.

To use a human voice instead: record each line as out/voice/<cue id>.wav, then run
`python build.py voice --keep` so the timeline follows the recordings.
"""

import base64
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
CUTS = {
    "kilowhat": (ROOT / "kilowhat", ROOT / "KiloWhat-promo.mp4"),
    "howitworks": (ROOT / "howitworks", ROOT / "KiloWhat-how-it-works.mp4"),
    "watttrace": (ROOT, ROOT / "WattTrace-promo.mp4"),
}
CUT = next((a.split("=", 1)[1] for a in sys.argv if a.startswith("--cut=")), "kilowhat")
if CUT not in CUTS:
    sys.exit(f"No cut {CUT!r}; the cuts are {', '.join(CUTS)}")
sys.argv = [a for a in sys.argv if not a.startswith("--cut=")]
CUT_DIR, VIDEO = CUTS[CUT]   # the finished video; everything in out/ can be rebuilt
OUT = CUT_DIR / "out"
VOICE_DIR = OUT / "voice"
PAGE = CUT_DIR / "video.html"
NARRATION = json.loads((CUT_DIR / "narration.json").read_text())
DURATION, FPS = float(NARRATION["duration"]), int(NARRATION["fps"])
WIDTH, HEIGHT = 1920, 1080
SR = 48000  # sample rate of the finished soundtrack

LEAD_IN_S = 0.55      # silence before the first line
TAIL_S = NARRATION.get("tail", 1.7)   # hold on the end card after the last line
MIN_GAP_S, MAX_GAP_S = 0.16, NARRATION.get("max_gap", 0.55)   # pause after a line; a cue's "pause" multiplies it
SCENE_GAP = 2.0       # pause weight between scenes, when the cue sets none
SCENE_LEAD_S = 0.5    # a scene is on screen this long before its first line
PAUSE_S = 0.11        # silence this long inside a line splits it into spoken segments
LOUDNESS_LUFS = NARRATION.get("loudness", -16)   # loudness of the finished soundtrack


def sound():
    """The cut's own music and sound effects (kilowhat/sound.py), or None for the first release."""
    if not (CUT_DIR / "sound.py").exists():
        return None
    sys.path.insert(0, str(CUT_DIR))
    import sound as module
    return module


def ffmpeg():
    import imageio_ffmpeg
    return imageio_ffmpeg.get_ffmpeg_exe()


def run(cmd, **kwargs):
    done = subprocess.run([str(c) for c in cmd], capture_output=True, text=True, **kwargs)
    if done.returncode:
        sys.exit(f"{Path(str(cmd[0])).name} failed:\n{done.stderr[-2000:]}")
    return done


# ---------- voice ----------

def _envelope(samples, sr, frame_s=0.01):
    """RMS level per 10 ms frame."""
    n = int(sr * frame_s)
    frames = samples[: len(samples) // n * n].reshape(-1, n)
    return np.sqrt((frames ** 2).mean(axis=1)), frame_s


def spoken_segments(samples, sr):
    """[(start s, end s)] of the stretches of speech in a clip, split at pauses of PAUSE_S or more."""
    env, step = _envelope(samples, sr)
    loud = env > max(env.max() * 0.045, 1e-4)
    segments, start, quiet = [], None, 0
    for i, on in enumerate(loud):
        if on:
            if start is None:
                start = i
            quiet = 0
        elif start is not None:
            quiet += 1
            if quiet * step >= PAUSE_S:
                segments.append((start * step, (i - quiet + 1) * step))
                start, quiet = None, 0
    if start is not None:
        segments.append((start * step, (len(loud) - quiet) * step))
    return [(round(a, 3), round(b, 3)) for a, b in segments if b - a >= 0.06]


def trim(samples, sr):
    """Cut the silence before and after the speech, keeping a short faded pad.

    The threshold is far below the one that finds pauses, so a soft first or last
    consonant ("h", "s", "f") stays in.
    """
    env, step = _envelope(samples, sr)
    heard = np.flatnonzero(env > env.max() * 0.012)
    if not len(heard):
        return samples
    a = max(int((heard[0] * step - 0.05) * sr), 0)
    b = min(int(((heard[-1] + 1) * step + 0.12) * sr), len(samples))
    clip = samples[a:b].copy()
    fade = int(0.008 * sr)
    clip[:fade] *= np.linspace(0, 1, fade)
    clip[-fade:] *= np.linspace(1, 0, fade)
    return clip


def synthesize():
    """One wav per cue in out/voice/, with the local Kokoro model, else macOS `say`."""
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    folder = os.environ.get("KOKORO_DIR")
    model = Path(folder) / "kokoro-v1.0.onnx" if folder else None
    if model and model.exists():
        import espeakng_loader
        from kokoro_onnx import EspeakConfig, Kokoro
        data = espeakng_loader.get_data_path()
        if len(data) > 150:
            # espeak-ng can't open a data folder with a path over 160 characters (a deep virtualenv).
            data = shutil.copytree(data, Path(tempfile.mkdtemp(prefix="espeak-")) / "data")
        kokoro = Kokoro(str(model), str(Path(folder) / "voices-v1.0.bin"),
                        espeak_config=EspeakConfig(data_path=str(data)))
        for cue in NARRATION["cues"]:
            samples, sr = kokoro.create(cue["say"], voice=cue.get("voice", NARRATION["voice"]),
                                        speed=cue.get("speed", NARRATION["speed"]), lang="en-us")
            sf.write(VOICE_DIR / f"{cue['id']}.wav", trim(np.asarray(samples, dtype=np.float32), sr), sr)
        return f"Kokoro ({NARRATION['voice']})"
    for cue in NARRATION["cues"]:
        aiff = VOICE_DIR / f"{cue['id']}.aiff"
        run(["say", "-v", "Samantha", "-r", "175", "-o", aiff, cue["say"]])
        run([ffmpeg(), "-y", "-i", aiff, "-ar", "24000", "-ac", "1", VOICE_DIR / f"{cue['id']}.wav"])
        aiff.unlink()
        samples, sr = sf.read(VOICE_DIR / f"{cue['id']}.wav", dtype="float32")
        sf.write(VOICE_DIR / f"{cue['id']}.wav", trim(samples, sr), sr)
    return "macOS say (Samantha)"


def build_timeline():
    """Place every line on the 60 s timeline and write out/timeline.json and out/timeline.js."""
    cues = []
    for cue in NARRATION["cues"]:
        samples, sr = sf.read(VOICE_DIR / f"{cue['id']}.wav", dtype="float32")
        if samples.ndim > 1:
            samples = samples.mean(axis=1)
        cues.append({**cue, "length": len(samples) / sr, "segments": spoken_segments(samples, sr)})

    # Pauses share whatever time the speech leaves, in proportion to their weights.
    weights = []
    for cue, nxt in zip(cues, cues[1:]):
        weights.append(cue.get("pause", SCENE_GAP if nxt["scene"] != cue["scene"] else 1.0))
    speech = sum(c["length"] for c in cues)
    spare = DURATION - LEAD_IN_S - TAIL_S - speech
    unit = spare / sum(weights)
    if unit < MIN_GAP_S:
        sys.exit(f"Speech takes {speech:.1f} s: too long for {DURATION:.0f} s. Cut words or raise \"speed\".")
    unit = min(unit, MAX_GAP_S)

    t, placed = LEAD_IN_S, []
    for i, cue in enumerate(cues):
        start, end = t, t + cue["length"]
        chunks = [c.strip() for c in cue["caption"].split("|")]
        total, at, captions = sum(len(c) for c in chunks), start, []
        for chunk in chunks:  # caption chunks share the line's time by their length
            upto = at + cue["length"] * len(chunk) / total
            captions.append({"text": chunk, "start": round(at, 3), "end": round(upto, 3)})
            at = upto
        placed.append({"id": cue["id"], "scene": cue["scene"], "start": round(start, 3), "end": round(end, 3),
                       "segments": [[round(start + a, 3), round(start + b, 3)] for a, b in cue["segments"]],
                       "captions": captions})
        t = end + (weights[i] * unit if i < len(weights) else 0)

    scenes = []
    for cue in placed:
        if not scenes or scenes[-1]["id"] != cue["scene"]:
            # Cut shortly before the next scene's first line, so the scene before it gets the pause.
            cut = 0.0 if not scenes else round(max(scenes[-1]["last"] + 0.25, cue["start"] - SCENE_LEAD_S), 3)
            if scenes:
                scenes[-1]["end"] = cut
            scenes.append({"id": cue["scene"], "start": cut, "end": DURATION})
        scenes[-1]["last"] = cue["end"]
    for scene in scenes:
        del scene["last"]

    timeline = {"duration": DURATION, "fps": FPS, "cues": placed, "scenes": scenes}
    OUT.mkdir(exist_ok=True)
    (OUT / "timeline.json").write_text(json.dumps(timeline, indent=1))
    (OUT / "timeline.js").write_text(f"window.TIMELINE = {json.dumps(timeline)};\n")
    words = sum(len(c["say"].split()) for c in cues)
    print(f"{words} words, {speech:.1f} s of speech, {unit:.2f} s per pause, last line ends at {placed[-1]['end']:.1f} s")
    for cue in placed:
        print(f"  {cue['start']:6.2f}-{cue['end']:6.2f}  {cue['id']:4} {cue['scene']:8} {len(cue['segments'])} segment(s)")
    return timeline


def voice_track(timeline):
    """The whole voice-over as one mono track at SR, each clip at its place."""
    track = np.zeros(int(DURATION * SR), dtype=np.float32)
    for cue in timeline["cues"]:
        resampled = OUT / "voice" / f"{cue['id']}.48k.wav"
        run([ffmpeg(), "-y", "-i", VOICE_DIR / f"{cue['id']}.wav", "-ar", SR, "-ac", "1", resampled])
        samples, _ = sf.read(resampled, dtype="float32")
        resampled.unlink()
        a = int(cue["start"] * SR)
        track[a:a + len(samples)] += samples[: len(track) - a]
    # Same loudness whichever voice made it: speech at about -19 dBFS RMS, peaks under -1.5 dBFS.
    env, _ = _envelope(track, SR)
    speech_rms = np.sqrt((env[env > env.max() * 0.05] ** 2).mean())
    track *= min(10 ** (-19 / 20) / speech_rms, 10 ** (-1.5 / 20) / np.abs(track).max())
    return track


def step_voice(keep=False):
    if not keep:
        print("Voice:", synthesize())
    timeline = build_timeline()
    sf.write(OUT / "voiceover.wav", voice_track(timeline), SR)
    write_srt(timeline)
    return timeline


def write_srt(timeline):
    def stamp(t):
        ms = int(round(t * 1000))
        return f"{ms // 3600000:02}:{ms // 60000 % 60:02}:{ms // 1000 % 60:02},{ms % 1000:03}"
    rows = [c for cue in timeline["cues"] for c in cue["captions"]]
    VIDEO.with_suffix(".srt").write_text("".join(
        f"{i}\n{stamp(c['start'])} --> {stamp(c['end'])}\n{c['text']}\n\n" for i, c in enumerate(rows, 1)))


# ---------- music ----------

def _note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def step_music(timeline=None):
    timeline = timeline or json.loads((OUT / "timeline.json").read_text())
    if sound():
        music = sound().music(timeline, SR)
        sf.write(OUT / "music.wav", music.astype(np.float32), SR)
        print(f"Music: {len(music) / SR:.0f} s, peak {20 * np.log10(np.abs(music).max()):.1f} dBFS")
        return
    step_pad_music(timeline)


def step_pad_music(timeline):
    """A quiet pad with a soft pulse, synthesized here so there's nothing to license.

    Eight chords across the minute, ending on the home chord. The pulse starts when the
    product is introduced and stops for the end card.
    """
    scene = {s["id"]: s for s in timeline["scenes"]}
    n = int(DURATION * SR)
    t = np.arange(n) / SR
    rng = np.random.default_rng(7)
    left, right = np.zeros(n), np.zeros(n)

    # (bass, pad notes) as MIDI numbers: Bm7, Gmaj7, Dadd9, Asus4, then again resolving to D.
    chords = [(35, (59, 62, 66, 69)), (31, (59, 62, 66, 67)), (38, (57, 62, 64, 66)), (33, (57, 62, 64, 69)),
              (35, (59, 62, 66, 69)), (31, (59, 62, 66, 67)), (33, (57, 61, 64, 69)), (38, (57, 62, 66, 69))]
    bar = DURATION / len(chords)
    for i, (bass, notes) in enumerate(chords):
        start = i * bar
        # Each chord swells in over 1.6 s and fades over the next chord's swell.
        env = np.clip((t - start + 0.4) / 1.6, 0, 1) * np.clip((start + bar + 1.4 - t) / 1.8, 0, 1)
        env = np.sin(env * np.pi / 2) ** 2
        for midi in notes:
            f = _note(midi)
            wobble = 1 + 0.12 * np.sin(2 * np.pi * rng.uniform(0.07, 0.16) * t + rng.uniform(0, 6.28))
            for cents, pan in ((-5, 0.25), (0, 0.5), (5, 0.75)):
                ff = f * 2 ** (cents / 1200)
                tone = np.sin(2 * np.pi * ff * t) + 0.22 * np.sin(4 * np.pi * ff * t) + 0.07 * np.sin(6 * np.pi * ff * t)
                tone *= env * wobble * 0.05
                left += tone * (1 - pan)
                right += tone * pan
        low = np.sin(2 * np.pi * _note(bass) * t) + 0.3 * np.sin(4 * np.pi * _note(bass) * t)
        left += low * env * 0.11
        right += low * env * 0.11

    # Pulse: one soft pluck every 0.3 s, walking up and down the chord, with an echo.
    pulse_on, pulse_off = scene["meet"]["start"], scene["close"]["start"]
    step = 0.3
    pattern = (0, 2, 1, 3, 2, 1)
    pl, pr = np.zeros(n), np.zeros(n)
    k = 0
    for start in np.arange(pulse_on, pulse_off + 1.2, step):
        notes = chords[min(int(start / bar), len(chords) - 1)][1]
        f = _note(notes[pattern[k % len(pattern)]] + 12)
        a, b = int(start * SR), min(int((start + 1.2) * SR), n)
        tt = t[a:b] - start
        pluck = (np.sin(2 * np.pi * f * tt) + 0.25 * np.sin(4 * np.pi * f * tt)) * np.exp(-tt / 0.16)
        pluck *= np.clip(tt / 0.004, 0, 1)
        swell = min((start - pulse_on) / 3.0, 1.0) * min(max((pulse_off + 1.2 - start) / 2.0, 0.0), 1.0)
        pan = 0.35 if k % 2 else 0.65
        pl[a:b] += pluck * 0.06 * swell * (1 - pan)
        pr[a:b] += pluck * 0.06 * swell * pan
        k += 1
    delay = int(0.45 * SR)
    for gain in (0.4, 0.16):  # echoes bounce side to side
        pl, pr = pl + gain * np.roll(pr, delay), pr + gain * np.roll(pl, delay)
        delay *= 2
    left += pl
    right += pr

    stereo = np.stack([left, right], axis=1)
    # One-pole low-pass at about 3 kHz takes the edge off.
    alpha = 1 - np.exp(-2 * np.pi * 3000 / SR)
    smooth = np.empty_like(stereo)
    acc = np.zeros(2)
    for i in range(n):
        acc += alpha * (stereo[i] - acc)
        smooth[i] = acc
    smooth *= (np.clip(t / 1.5, 0, 1) * np.clip((DURATION - t) / 2.5, 0, 1))[:, None]
    smooth *= 10 ** (-30 / 20) / np.sqrt((smooth ** 2).mean())   # well under the voice (about -19 dBFS)
    sf.write(OUT / "music.wav", smooth.astype(np.float32), SR)
    print(f"Music: {DURATION:.0f} s, peak {20 * np.log10(np.abs(smooth).max()):.1f} dBFS")


# ---------- frames ----------

def _page(playwright):
    browser = playwright.chromium.launch(channel="chrome", headless=True)
    page = browser.new_context(viewport={"width": WIDTH, "height": HEIGHT}, device_scale_factor=1).new_page()
    page.on("console", lambda m: print("  page:", m.text) if m.type in ("error", "warning") else None)
    page.on("pageerror", lambda e: print("  page error:", e))
    page.goto(PAGE.as_uri() + "?render=1")
    page.wait_for_function("window.READY === true", timeout=20000)
    return browser, page


def _capture(page, cdp, t):
    page.evaluate("t => window.seek(t)", t)
    shot = cdp.send("Page.captureScreenshot", {"format": "png", "optimizeForSpeed": True})
    return base64.b64decode(shot["data"])


def step_still(times):
    from playwright.sync_api import sync_playwright
    (OUT / "stills").mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser, page = _page(p)
        cdp = page.context.new_cdp_session(page)
        for t in times:
            path = OUT / "stills" / f"{t:05.2f}.png"
            path.write_bytes(_capture(page, cdp, t))
            print("still", path.name)
        browser.close()


def step_sfx():
    """The sound effects video.html places (window.SFX: when, which, how loud, where in the stereo field)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser, page = _page(p)
        cues = page.evaluate("window.SFX")
        browser.close()
    track = sound().effects(cues, DURATION, SR)
    sf.write(OUT / "sfx.wav", track.astype(np.float32), SR)
    print(f"Sound effects: {len(cues)}, peak {20 * np.log10(np.abs(track).max()):.1f} dBFS")


def step_frames():
    from playwright.sync_api import sync_playwright
    total = int(round(DURATION * FPS))
    encoder = subprocess.Popen(
        [ffmpeg(), "-y", "-loglevel", "error", "-f", "image2pipe", "-framerate", str(FPS), "-c:v", "png", "-i", "-",
         "-c:v", "libx264", "-preset", "slow", "-crf", "15", "-pix_fmt", "yuv420p",
         "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709", str(OUT / "silent.mp4")],
        stdin=subprocess.PIPE)
    with sync_playwright() as p:
        browser, page = _page(p)
        cdp = page.context.new_cdp_session(page)
        for i in range(total):
            encoder.stdin.write(_capture(page, cdp, i / FPS))
            if i % 150 == 0:
                print(f"  frame {i}/{total}", flush=True)
        browser.close()
    encoder.stdin.close()
    if encoder.wait():
        sys.exit("ffmpeg failed while encoding frames")
    print(f"Frames: {total} at {FPS} fps")


# ---------- mux ----------

def step_mux():
    """Voice over the music (which dips while someone is speaking), onto the frames."""
    inputs = ["-i", OUT / "voiceover.wav", "-i", OUT / "music.wav"]
    mix = ("[0:a]pan=stereo|c0=c0|c1=c0,asplit=2[voice][key];"
           "[1:a][key]sidechaincompress=threshold=0.05:ratio=3:attack=20:release=700[bed];"
           "[voice][bed]amix=inputs=2:normalize=0[a]")
    if sound():   # the sound effects sit under the voice too, a little less than the music
        inputs += ["-i", OUT / "sfx.wav"]
        mix = ("[0:a]pan=stereo|c0=c0|c1=c0,asplit=3[voice][key][key2];"
               "[1:a][key]sidechaincompress=threshold=0.05:ratio=3:attack=20:release=600[bed];"
               "[2:a][key2]sidechaincompress=threshold=0.05:ratio=1.6:attack=10:release=300[fx];"
               "[voice][bed][fx]amix=inputs=3:normalize=0[a]")
    run([ffmpeg(), "-y", *inputs, "-filter_complex", mix, "-map", "[a]", "-ar", SR, OUT / "mix.wav"])
    # Bring the mix to LOUDNESS_LUFS, the level video sites play at, and catch the peaks that pushes over.
    # The limiter runs at 4x the sample rate, where the peaks between samples show up too.
    measured = run([ffmpeg(), "-hide_banner", "-nostats", "-i", OUT / "mix.wav", "-af", "ebur128", "-f", "null", "-"])
    loudness = float(re.findall(r"I:\s+(-?[\d.]+) LUFS", measured.stderr)[-1])
    master = (f"volume={LOUDNESS_LUFS - loudness:.2f}dB,aresample={SR * 4},"
              f"alimiter=limit=0.84:attack=3:release=60:level=disabled,aresample={SR}")
    run([ffmpeg(), "-y", "-i", OUT / "silent.mp4", "-i", OUT / "mix.wav", "-af", master, "-map", "0:v", "-map", "1:a",
         "-c:v", "copy", "-c:a", "aac", "-b:a", "192k", "-ar", SR, "-t", DURATION, "-movflags", "+faststart", VIDEO])
    run([ffmpeg(), "-y", "-i", VIDEO, "-vn", "-c:a", "copy", OUT / "audio.m4a"])   # for the preview in video.html
    print(f"Wrote {VIDEO} (mix was {loudness:.1f} LUFS, now about {LOUDNESS_LUFS})")


if __name__ == "__main__":
    step, args = (sys.argv[1] if len(sys.argv) > 1 else "all"), sys.argv[2:]
    if step == "voice":
        step_voice(keep="--keep" in args)
    elif step == "music":
        step_music()
    elif step == "still":
        step_still([float(a) for a in args])
    elif step == "sfx":
        step_sfx()
    elif step == "frames":
        step_frames()
    elif step == "mux":
        step_mux()
    elif step == "all":
        step_music(step_voice(keep="--keep" in args))
        if sound():
            step_sfx()
        step_frames()
        step_mux()
    else:
        sys.exit(__doc__)
