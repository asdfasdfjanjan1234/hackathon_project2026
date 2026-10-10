"""Music and sound effects for the Kilo What? promo, synthesized here so there's nothing to license.

build.py calls music(timeline, sr) and effects(cues, duration, sr); both return stereo float arrays.
Another cut can have the same score follow its own story with score() (howitworks/sound.py does).

The music follows the story, not fixed seconds:
  hook, guess   a low drone in D minor with a meter-like tick; tension, no beat
  $meet         the bolt lands on the downbeat: kick, pumping bass, pad, arpeggio (120 BPM)
  $sense        hats come in; $verdict claps come in
  fix#1         the "Switch now" click: everything but the pad drops out for a bar
  $close        the beat stops on a final F major chord that rings out
"""
import numpy as np

BPM = 120
BEAT = 60 / BPM
RNG = np.random.default_rng(11)


def _note(midi):
    return 440.0 * 2 ** ((midi - 69) / 12)


def _filt(x, kind, freq, sr, order=2):
    """Butterworth-shaped low-, high- or band-pass, applied in the frequency domain (zero phase).

    Padded with silence first, so a tail doesn't wrap round to the start.
    """
    n = len(x)
    pad = min(n, int(0.25 * sr))
    X = np.fft.rfft(np.concatenate([x, np.zeros((pad,) + x.shape[1:])]), axis=0)
    f = np.maximum(np.fft.rfftfreq(n + pad, 1 / sr), 1e-6)
    lp = lambda fc: 1 / np.sqrt(1 + (f / fc) ** (2 * order))
    hp = lambda fc: 1 / np.sqrt(1 + (fc / f) ** (2 * order))
    H = {"lowpass": lambda: lp(freq), "highpass": lambda: hp(freq),
         "bandpass": lambda: hp(freq[0]) * lp(freq[1])}[kind]()
    if x.ndim == 2:
        H = H[:, None]
    return np.fft.irfft(X * H, n=n + pad, axis=0)[:n]


def fftconvolve(a, b):
    n = len(a) + len(b) - 1
    return np.fft.irfft(np.fft.rfft(a, n) * np.fft.rfft(b, n), n)


def _saw(phase):
    return 2 * (phase % 1.0) - 1


def _sweep(f0, f1, dur, sr, curve="exp"):
    """Phase (in cycles) of a tone gliding from f0 to f1."""
    t = np.arange(int(dur * sr)) / sr
    f = f0 * (f1 / f0) ** (t / dur) if curve == "exp" else f0 + (f1 - f0) * t / dur
    return np.cumsum(f) / sr, t


def _place(track, clip, start, sr, gain=1.0, pan=0.0):
    """Add a mono or stereo clip to a stereo track at `start` seconds, panned -1..1 (equal power)."""
    if clip.ndim == 1:
        a = np.pi / 4 * (1 + np.clip(pan, -1, 1))
        clip = np.stack([clip * np.cos(a), clip * np.sin(a)], axis=1) * np.sqrt(2)
    i = int(round(start * sr))
    if i < 0:
        clip, i = clip[-i:], 0
    n = min(len(clip), len(track) - i)
    if n > 0:
        track[i:i + n] += clip[:n] * gain


def _reverb(x, sr, seconds=2.2, decay=0.55, tone=5000):
    """A plate-ish reverb: stereo decaying noise as the impulse response."""
    n = int(seconds * sr)
    t = np.arange(n) / sr
    ir = RNG.standard_normal((n, 2)) * np.exp(-t / decay)[:, None]
    ir = _filt(ir, "lowpass", tone, sr)
    ir[: int(0.012 * sr)] = 0   # a short pre-delay keeps the dry sound clear
    ir /= np.sqrt((ir ** 2).sum(axis=0))
    if x.ndim == 1:
        x = np.stack([x, x], axis=1)
    return np.stack([fftconvolve(x[:, c], ir[:, c])[: len(x)] for c in range(2)], axis=1)


def _env(t, attack, release_at, release):
    return np.clip(t / attack, 0, 1) * np.clip((release_at - t) / release, 0, 1)


# ---------- music ----------

# One bar per chord (2 s at 120 BPM): Dm9, Bbmaj7, F, Csus. (bass, pad, arpeggio tones)
CHORDS = [
    (38, (50, 53, 57, 64), (62, 65, 69, 72, 76)),
    (34, (50, 53, 58, 62), (58, 62, 65, 70, 74)),
    (41, (48, 53, 57, 60), (60, 65, 69, 72, 77)),
    (36, (48, 52, 55, 62), (60, 64, 67, 72, 74)),
]
FINAL = (29, (53, 57, 60, 65, 67), ())   # F major add9, low F underneath


def music(timeline, sr):
    scene = {s["id"]: s for s in timeline["scenes"]}
    cue = {c["id"]: c for c in timeline["cues"]}
    fix = cue["fix"]["segments"]
    return score(float(timeline["duration"]), sr, t0=scene["meet"]["start"], t_close=scene["close"]["start"],
                 t_click=fix[1][0] if len(fix) > 1 else cue["fix"]["start"] + 1.0,
                 hats_on=scene["sense"]["start"], claps_on=scene["verdict"]["start"], t_open=scene["guess"]["start"])


def score(T, sr, t0, t_close, t_click, hats_on, claps_on, t_open):
    """The score, placed by the story's moments (seconds): t0 the bolt and first downbeat, t_open
    when the intro drone has opened up, hats_on and claps_on when they join, t_click where
    everything but the pad drops out until a bar line, t_close the final chord."""
    n = int(T * sr)
    t = np.arange(n) / sr
    t_back = t0 + np.ceil((t_click + 1.0 - t0) / (4 * BEAT)) * 4 * BEAT   # the beat returns on a bar line

    dry = np.zeros((n, 2))
    wet = np.zeros((n, 2))   # sent to the reverb

    def grooving(x):
        return t0 <= x < t_close and not (t_click <= x < t_back)

    # Sidechain: everything but the kick dips after each kick, so the groove pumps.
    since = np.where(t >= t0, (t - t0) % BEAT, 9.0)
    groove_mask = np.array([(t0 <= x < t_close) and not (t_click <= x < t_back) for x in t[:: sr // 100]])
    groove_mask = np.repeat(groove_mask, sr // 100)[:n]
    if len(groove_mask) < n:
        groove_mask = np.pad(groove_mask, (0, n - len(groove_mask)), constant_values=False)
    duck = 1 - 0.55 * np.exp(-since / 0.13) * np.clip(since / 0.004, 0, 1) * groove_mask

    # --- intro drone: D minor, swelling with the bill, closing down before the bolt ---
    intro_env = np.clip(t / 1.5, 0, 1) * np.clip((t0 - 0.18 - t) / 0.12, 0, 1)
    for midi, g in ((38, 0.5), (50, 0.28), (57, 0.2), (64, 0.1)):
        f = _note(midi)
        wob = 1 + 0.15 * np.sin(2 * np.pi * RNG.uniform(0.1, 0.25) * t)
        tone = sum(_saw(f * (1 + d) * t + RNG.uniform()) for d in (-0.003, 0, 0.003)) / 3
        dry += (tone * g * wob * intro_env)[:, None] * [0.5, 0.5]
    # The drone's filter opens as the bill climbs, then closes during the guess.
    cutoff_lo = _filt(dry, "lowpass", 380, sr)
    cutoff_hi = _filt(dry, "lowpass", 1400, sr)
    open_amt = np.clip(t / t_open, 0, 1) * np.clip((t0 - t) / 2.0, 0, 1)
    dry = cutoff_lo * (1 - open_amt[:, None]) + cutoff_hi * open_amt[:, None]
    dry *= 0.9

    # Meter ticks on the 8ths during the intro, on the same grid the beat will use.
    tick = _filt(RNG.standard_normal(int(0.03 * sr)), "highpass", 5000, sr) * np.exp(-np.arange(int(0.03 * sr)) / sr / 0.006)
    k = 0
    for x in np.arange(t0 - BEAT / 2, 0, -BEAT / 2)[::-1]:
        if 0.6 < x < t0 - 0.3:
            _place(dry, tick, x, sr, gain=0.10 * (0.6 + 0.4 * (k % 2)) * min(x / 3, 1), pan=0.3 if k % 2 else -0.2)
            k += 1

    # --- pad: detuned saws per chord, lowpassed, through the reverb ---
    bars = np.arange(t0, t_close, 4 * BEAT)
    for b, start in enumerate(bars):
        bass, pad, arp = CHORDS[b % len(CHORDS)]
        end = min(start + 4 * BEAT, t_close)
        a, z = int(start * sr), int(min(end + 0.6, T) * sr)
        tt = t[a:z] - start
        env = _env(tt, 0.25, end - start + 0.5, 0.6)
        voice = np.zeros((z - a, 2))
        for midi in pad:
            f = _note(midi)
            for d, p in ((-0.006, 0.2), (0, 0.5), (0.006, 0.8)):
                s = _saw(f * (1 + d) * tt + RNG.uniform())
                voice += np.outer(s, [1 - p, p])
        voice = _filt(voice, "lowpass", 1500, sr) * env[:, None] * 0.07
        dry[a:z] += voice * duck[a:z, None]
        wet[a:z] += voice * 0.8

        # Bass: 8ths on the root, a saw rounded off by a lowpass, pumping with the kick.
        for i in range(8):
            x = start + i * BEAT / 2
            if not grooving(x):
                continue
            L = int(BEAT / 2 * sr)
            tb = np.arange(L) / sr
            f = _note(bass)
            s = _saw(f * tb) * 0.6 + np.sin(2 * np.pi * f * tb)
            s *= np.clip(tb / 0.005, 0, 1) * np.clip((BEAT / 2 - tb) / 0.03, 0, 1)
            _place(dry, _filt(s, "lowpass", 520, sr) * 0.30, x, sr)

        # Arpeggio: 16ths walking the chord, from the product reveal to the close.
        pattern = (0, 2, 1, 3, 2, 4, 3, 1)
        for i in range(16):
            x = start + i * BEAT / 4
            if not grooving(x) or not arp:
                continue
            f = _note(arp[pattern[i % len(pattern)] % len(arp)])
            L = int(0.32 * sr)
            tb = np.arange(L) / sr
            s = (np.sign(np.sin(2 * np.pi * f * tb)) * 0.35 + np.sin(2 * np.pi * f * tb)) * np.exp(-tb / 0.09)
            s = _filt(s * np.clip(tb / 0.002, 0, 1), "lowpass", 2600, sr)
            level = 0.045 * min((x - t0) / 6.0, 1.0)
            pan = -0.45 if i % 2 else 0.45
            _place(dry, s, x, sr, gain=level, pan=pan)
            _place(wet, s, x, sr, gain=level * 0.9, pan=pan)

    # --- drums ---
    L = int(0.45 * sr)
    tk = np.arange(L) / sr
    kick_phase = np.cumsum(46 + 120 * np.exp(-tk / 0.028)) / sr
    kick = np.sin(2 * np.pi * kick_phase) * np.exp(-tk / 0.22)
    kick += _filt(RNG.standard_normal(L), "highpass", 2000, sr) * np.exp(-tk / 0.004) * 0.25
    kick = np.tanh(kick * 1.6) * 0.55

    Lh = int(0.08 * sr)
    th = np.arange(Lh) / sr
    hat = _filt(RNG.standard_normal(Lh), "highpass", 7500, sr) * np.exp(-th / 0.022) * 0.16

    Lc = int(0.3 * sr)
    tc = np.arange(Lc) / sr
    burst = sum(np.exp(-np.clip(tc - d, 0, None) / 0.012) * (tc >= d) for d in (0, 0.011, 0.023))
    clap = _filt(RNG.standard_normal(Lc), "bandpass", (900, 3200), sr) * (burst + np.exp(-tc / 0.12) * 0.6) * 0.17

    beats = np.arange(t0, t_close, BEAT)
    for i, x in enumerate(beats):
        if not grooving(x):
            continue
        _place(dry, kick, x, sr)
        if x >= hats_on:
            _place(dry, hat, x + BEAT / 2, sr, pan=0.25)
            _place(dry, hat * 0.45, x + BEAT * 0.75, sr, pan=0.35)
        if x >= claps_on and i % 2 == 1:
            _place(dry, clap, x, sr, pan=-0.05)
            _place(wet, clap, x, sr, gain=0.6)
    # A snare fill leads the beat back in after the break.
    for j in range(8):
        x = t_back - BEAT * 2 + j * BEAT / 4
        _place(dry, clap * (0.35 + 0.08 * j), x, sr, pan=-0.3 + 0.08 * j)

    # --- the end: F major add9 rings out from the close ---
    bass, pad, _ = FINAL
    a = int(t_close * sr)
    tt = t[a:] - t_close
    env = np.clip(tt / 0.02, 0, 1) * np.exp(-tt / 3.2)
    chord = np.zeros((n - a, 2))
    for j, midi in enumerate(pad):
        f = _note(midi)
        for d, p in ((-0.005, 0.25), (0.005, 0.75)):
            chord += np.outer(_saw(f * (1 + d) * tt + RNG.uniform()), [1 - p, p])
        chord += np.outer(np.sin(2 * np.pi * 2 * f * tt) * 0.3 * np.exp(-tt / 1.2), [0.5, 0.5])   # a bell on top
    chord = _filt(chord, "lowpass", 2200, sr) * env[:, None] * 0.085
    sub = np.sin(2 * np.pi * _note(bass + 12) * tt) * env * 0.35
    dry[a:] += chord + sub[:, None] * [0.5, 0.5]
    wet[a:] += chord * 1.2

    mix = dry + _reverb(wet, sr) * 0.55
    mix *= (np.clip(t / 0.3, 0, 1) * np.clip((T - t) / 0.4, 0, 1))[:, None]
    mix = _filt(mix, "highpass", 28, sr)
    rms = np.sqrt((mix[t > t0] ** 2).mean())
    mix *= 10 ** (-25 / 20) / rms                 # the groove at about -25 dBFS RMS, well under the voice
    peak = np.abs(mix).max()
    if peak > 0.89:
        mix = np.tanh(mix / 0.89) * 0.89             # soft-clip the odd peak
    return mix


# ---------- sound effects ----------

def _noise(dur, sr):
    return RNG.standard_normal(int(dur * sr))


def _swept_band(noise, sr, centers, q=1.2):
    """Noise through a band-pass whose centre moves through `centers` over the clip (crossfaded bands)."""
    n = len(noise)
    out = np.zeros(n)
    pos = np.linspace(0, 1, n)
    k = len(centers)
    for i, c in enumerate(centers):
        lo, hi = c / (1 + 0.5 / q), min(c * (1 + 0.5 / q), sr / 2 * 0.95)
        band = _filt(noise, "bandpass", (lo, hi), sr)
        w = np.clip(1 - np.abs(pos * (k - 1) - i), 0, 1)
        out += band * w
    return out


def fx_hit(sr, **_):
    """The bolt: a sub drop, a crack and a falling electric zap."""
    ph, t = _sweep(140, 34, 1.4, sr)
    sub = np.sin(2 * np.pi * ph) * np.exp(-t / 0.42)
    crack = _filt(_noise(1.4, sr), "highpass", 1800, sr) * np.exp(-t / 0.025)
    zph, _ = _sweep(2600, 110, 1.4, sr)
    crackle = 1 + 0.8 * (RNG.random(len(t)) > 0.7)
    zap = _saw(zph) * np.exp(-t / 0.11) * crackle
    zap = _filt(zap, "lowpass", 6000, sr)
    x = sub * 0.9 + crack * 0.7 + zap * 0.35
    return np.tanh(x * 1.3) * 0.8


def fx_zap(sr, **_):
    zph, t = _sweep(3000, 300, 0.35, sr)
    crackle = 1 + 0.9 * (RNG.random(len(t)) > 0.75)
    return _filt(_saw(zph) * np.exp(-t / 0.07) * crackle, "lowpass", 7000, sr) * 0.4


def fx_whoosh(sr, dur=0.55, up=True, **_):
    noise = _noise(dur, sr)
    centers = np.geomspace(350, 3200, 8) if up else np.geomspace(3200, 350, 8)
    x = _swept_band(noise, sr, centers)
    t = np.arange(len(x)) / sr
    env = np.sin(np.pi * np.clip(t / dur, 0, 1)) ** 2
    return x * env * 0.5


def fx_riser(sr, dur=1.6, **_):
    noise = _noise(dur, sr)
    x = _swept_band(noise, sr, np.geomspace(250, 7000, 12), q=2)
    ph, t = _sweep(160, 1100, dur, sr)
    tone = np.sin(2 * np.pi * ph + 0.3 * np.sin(2 * np.pi * 6 * t)) * 0.25
    env = (t / dur) ** 2.2
    return (x * 0.7 + tone) * env * 0.55


def fx_pop(sr, pitch=1.0, **_):
    ph, t = _sweep(420 * pitch, 900 * pitch, 0.09, sr)
    x = np.sin(2 * np.pi * ph) * np.exp(-t / 0.035) * np.clip(t / 0.002, 0, 1)
    return x * 0.45


def fx_tick(sr, **_):
    t = np.arange(int(0.04 * sr)) / sr
    click = _filt(_noise(0.04, sr), "highpass", 3000, sr) * np.exp(-t / 0.003)
    ring = np.sin(2 * np.pi * 3300 * t) * np.exp(-t / 0.008)
    return (click * 0.5 + ring * 0.25) * 0.6


def fx_ticker(sr, dur=1.5, **_):
    """A counter rolling: ticks that start fast and slow to a stop."""
    out = np.zeros(int((dur + 0.1) * sr))
    tick = fx_tick(sr)
    x, k = 0.0, 0
    while x < dur:
        gap = 0.032 + 0.07 * (x / dur) ** 2
        i = int(x * sr)
        out[i:i + len(tick)] += tick[: len(out) - i] * (0.55 + 0.45 * (k % 2))
        x += gap
        k += 1
    return out * 0.7


def fx_ping(sr, **_):
    t = np.arange(int(0.9 * sr)) / sr
    f = 1568
    x = (np.sin(2 * np.pi * f * t) + 0.2 * np.sin(2 * np.pi * 2 * f * t)) * np.exp(-t / 0.22) * np.clip(t / 0.003, 0, 1)
    d = int(0.16 * sr)
    x[d:] += x[:-d] * 0.3
    return x * 0.22


def fx_glitch(sr, dur=1.4, **_):
    out = np.zeros(int(dur * sr))
    x = 0.0
    while x < dur:
        seg = RNG.uniform(0.025, 0.07)
        f = RNG.uniform(180, 1800)
        L = int(seg * sr)
        t = np.arange(L) / sr
        s = np.sign(np.sin(2 * np.pi * f * t))
        s = np.round(s * RNG.uniform(0.2, 1) * 4) / 4   # crushed
        s *= np.clip(t / 0.002, 0, 1) * np.clip((seg - t) / 0.004, 0, 1)
        i = int(x * sr)
        out[i:i + L] += s[: len(out) - i] * RNG.uniform(0.3, 1)
        x += seg + RNG.uniform(0.0, 0.05)
    return _filt(out, "lowpass", 4500, sr) * 0.13


def fx_stamp(sr, **_):
    ph, t = _sweep(110, 48, 0.4, sr)
    thump = np.sin(2 * np.pi * ph) * np.exp(-t / 0.07)
    slap = _filt(_noise(0.4, sr), "lowpass", 1600, sr) * np.exp(-t / 0.02)
    return (thump * 0.8 + slap * 0.6) * 0.75


def fx_drop(sr, **_):
    """'Is it?': the floor falls away."""
    ph, t = _sweep(90, 28, 1.8, sr)
    sub = np.sin(2 * np.pi * ph) * np.exp(-t / 0.7) * np.clip(t / 0.01, 0, 1)
    air = _swept_band(_noise(1.8, sr), sr, np.geomspace(2500, 200, 6)) * np.exp(-t / 0.4)
    return (sub * 0.85 + air * 0.25) * 0.8


def fx_hum(sr, dur=6.0, **_):
    """Mains hum (60 Hz in the Philippines) that grows with the bill, then cuts out."""
    t = np.arange(int(dur * sr)) / sr
    base = sum(a * np.sin(2 * np.pi * 60 * h * t) for h, a in ((1, 1), (2, 0.6), (3, 0.35), (5, 0.12)))
    buzz = np.tanh(np.sin(2 * np.pi * 120 * t) * 3) * 0.12
    level = 0.25 + 0.75 * np.clip(t / (dur * 0.8), 0, 1) ** 1.5
    env = np.clip(t / 0.4, 0, 1) * np.clip((dur - t) / 0.03, 0, 1)
    return (base + buzz) * level * env * 0.09


def fx_surge(sr, dur=2.0, **_):
    """Load coming on: a hum that rises in pitch and level."""
    ph, t = _sweep(50, 95, dur, sr)
    x = sum(a * np.sin(2 * np.pi * h * ph) for h, a in ((1, 1), (2, 0.55), (3, 0.3), (4, 0.15)))
    x += np.tanh(np.sin(2 * np.pi * 2 * ph) * 4) * 0.15
    env = np.clip(t / dur, 0, 1) ** 1.3 * np.clip((dur + 0.3 - t) / 0.3, 0, 1)
    return x * env * 0.22


def fx_thunk(sr, **_):
    ph, t = _sweep(85, 40, 0.6, sr)
    body = np.sin(2 * np.pi * ph) * np.exp(-t / 0.12)
    click = _filt(_noise(0.6, sr), "bandpass", (1200, 5000), sr) * np.exp(-t / 0.005)
    return np.tanh((body + click * 0.5) * 1.4) * 0.7


def fx_relay(sr, **_):
    """'Switch now': a relay snapping over."""
    L = int(0.4 * sr)
    t = np.arange(L) / sr
    out = np.zeros(L)
    for d, g in ((0.0, 1.0), (0.028, 0.7)):
        tt = np.clip(t - d, 0, None)
        on = t >= d
        out += on * g * (_filt(_noise(0.4, sr), "bandpass", (1500, 6000), sr) * np.exp(-tt / 0.005) * 0.8
                         + np.sin(2 * np.pi * 2300 * tt) * np.exp(-tt / 0.025) * 0.25)
    ph, _ = _sweep(75, 45, 0.4, sr)
    out += np.sin(2 * np.pi * ph) * np.exp(-t / 0.07) * 0.8
    return out * 0.75


def fx_powerdown(sr, dur=1.1, **_):
    ph, t = _sweep(340, 42, dur, sr)
    x = _filt(_saw(ph) * 0.6 + np.sin(2 * np.pi * ph), "lowpass", 1400, sr)
    env = (1 - t / dur) ** 1.6 * np.clip(t / 0.01, 0, 1)
    return x * env * 0.3


def fx_chime(sr, **_):
    L = int(1.6 * sr)
    t = np.arange(L) / sr
    out = np.zeros(L)
    for f0, d in ((1318.5, 0.0), (1975.5, 0.11)):
        tt = np.clip(t - d, 0, None)
        on = t >= d
        for ratio, a, dec in ((1, 1, 0.9), (2.0, 0.35, 0.5), (2.76, 0.25, 0.35), (5.4, 0.12, 0.15)):
            out += on * a * np.sin(2 * np.pi * f0 * ratio * tt) * np.exp(-tt / dec) * np.clip(tt / 0.002, 0, 1)
    return out * 0.12


def fx_type(sr, dur=1.0, **_):
    out = np.zeros(int((dur + 0.05) * sr))
    x = 0.0
    while x < dur:
        L = int(0.02 * sr)
        t = np.arange(L) / sr
        f = RNG.uniform(1800, 3200)
        s = (_filt(_noise(0.02, sr), "bandpass", (f * 0.7, f * 1.3), sr) * np.exp(-t / 0.004))
        i = int(x * sr)
        out[i:i + L] += s * RNG.uniform(0.5, 1)
        x += RNG.uniform(0.045, 0.11)
    return out * 0.35


EFFECTS = {name[3:]: fn for name, fn in globals().items() if name.startswith("fx_")}


def effects(cues, duration, sr):
    """cues: [{t, kind, gain?, pan?, dur?, pitch?, up?}] from video.html (window.SFX)."""
    track = np.zeros((int(duration * sr), 2))
    for c in cues:
        kind = c["kind"]
        if kind not in EFFECTS:
            raise SystemExit(f"video.html asks for a sound effect {kind!r} that sound.py doesn't have")
        params = {k: c[k] for k in ("dur", "pitch", "up") if c.get(k) is not None}
        clip = EFFECTS[kind](sr, **params)
        _place(track, clip, c["t"], sr, gain=c.get("gain", 1.0), pan=c.get("pan", 0.0))
    wet = _reverb(track, sr, seconds=1.4, decay=0.3, tone=6000)
    track = track + wet * 0.18
    peak = np.abs(track).max()
    if peak > 0.89:
        track = np.tanh(track / 0.89) * 0.89
    return track
