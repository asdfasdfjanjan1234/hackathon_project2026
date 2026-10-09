"""Checkpoints: every fitted candidate is saved as soon as it finishes.

A training run fits many models one after another (6 structures on Luzon; for a device, several
candidates per AI agent). Each result goes to its own JSON file in the run's checkpoint folder:
the fitted coefficients, the held-out forecasts and the scores. If the run is interrupted, or run
again, a candidate whose checkpoint matches is loaded instead of fitted again.

A checkpoint matches when its key does: a fingerprint of the exact data, the model structure, the
starting coefficients and the settings that affect the fit. Change any of them and it's refitted.
The folder also holds config.json, the configuration of the run that last wrote to it.
"""

import hashlib
import json
import os
import re

import numpy as np


def fingerprint(y, **settings):
    """A short hash of an hourly series (values, missing hours, time range) and the fit's settings."""
    h = hashlib.sha1()
    h.update(np.nan_to_num(y.to_numpy(dtype=float), nan=-1.0).round(9).tobytes())
    h.update(f"{y.index[0]}|{y.index[-1]}|{len(y)}".encode())
    h.update(json.dumps(settings, sort_keys=True, default=str).encode())
    return h.hexdigest()[:16]


def slug(*parts):
    return "__".join(re.sub(r"[^a-z0-9]+", "-", str(p).lower()).strip("-") for p in parts)


class Checkpoints:
    """A folder of checkpoints. With enabled=False nothing is read or written."""

    def __init__(self, folder, enabled=True, fresh=False):
        self.folder, self.enabled, self.fresh = folder, enabled, fresh
        self.loaded, self.saved = [], []

    def _path(self, name):
        return os.path.join(self.folder, f"{name}.json")

    def load(self, name, key):
        """The checkpoint called `name` if it was made with the same key, else None. `fresh` runs
        ignore what's there and overwrite it."""
        if not self.enabled or self.fresh or not os.path.exists(self._path(name)):
            return None
        try:
            with open(self._path(name)) as f:
                data = json.load(f)
        except (OSError, json.JSONDecodeError):
            return None  # a half-written file from a run that was killed: fit again
        if data.get("key") != key:
            return None
        self.loaded.append(name)
        return data

    def save(self, name, key, payload):
        if not self.enabled:
            return
        os.makedirs(self.folder, exist_ok=True)
        tmp = self._path(name) + ".tmp"
        with open(tmp, "w") as f:
            json.dump({"key": key, **payload}, f, indent=2)
        os.replace(tmp, self._path(name))  # the file appears complete or not at all
        self.saved.append(name)

    def save_config(self, snapshot):
        if not self.enabled:
            return
        os.makedirs(self.folder, exist_ok=True)
        with open(os.path.join(self.folder, "config.json"), "w") as f:
            json.dump(snapshot, f, indent=2)

    def summary(self):
        """Counts for the run record. The folder is given relative to the training folder, so a
        committed model file doesn't carry a path from someone's computer."""
        root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        folder = os.path.relpath(self.folder, root) if self.folder.startswith(root) else os.path.basename(self.folder)
        return {"folder": folder if self.enabled else None,
                "fitted": len(self.saved), "from_checkpoint": len(self.loaded)}
