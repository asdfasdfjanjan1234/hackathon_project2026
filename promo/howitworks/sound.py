"""Music and sound effects for the "how it works" cut: the Kilo What? promo's score and effects
(kilowhat/sound.py), following this cut's story.

  hook       the low drone and meter tick; tension, no beat
  $meet      the bolt lands in the mark on the downbeat: kick, bass, pad, arpeggio
  $read      hats come in; $see claps come in
  $fix       the verdict: everything but the pad drops out, and returns on a bar line
  $close     the bolt again: the beat stops on the final chord
"""
import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location("kilowhat_sound", Path(__file__).resolve().parent.parent / "kilowhat" / "sound.py")
shared = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(shared)

effects = shared.effects


def music(timeline, sr):
    scene = {s["id"]: s for s in timeline["scenes"]}
    cue = {c["id"]: c for c in timeline["cues"]}
    return shared.score(float(timeline["duration"]), sr, t0=scene["meet"]["start"], t_close=scene["close"]["start"],
                        t_click=scene["fix"]["start"], hats_on=scene["read"]["start"], claps_on=scene["see"]["start"],
                        t_open=cue["nobody"]["start"])
