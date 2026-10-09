"""Paths and settings shared by the training scripts."""

import os
import sys

from .config import CONFIG

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
BACKEND_DIR = os.path.join(os.path.dirname(os.path.dirname(ROOT)), "backend")
# The scripts reuse the backend's database access, .env config and tariff code.
if BACKEND_DIR not in sys.path:
    sys.path.insert(0, BACKEND_DIR)

RAW_IEMOP = os.path.join(ROOT, "data", "raw", "iemop")
PROCESSED = os.path.join(ROOT, "data", "processed")
LUZON_DEMAND = os.path.join(PROCESSED, "luzon_demand.csv")

ARTIFACTS = os.path.join(ROOT, "artifacts")
LUZON_DIR = os.path.join(ARTIFACTS, "luzon")      # public grid data: fine to commit
LUZON_MODEL = os.path.join(LUZON_DIR, "luzon_pretrained.json")
LUZON_CHECKPOINTS = os.path.join(LUZON_DIR, "checkpoints")
DEVICE_DIR = os.path.join(ARTIFACTS, "devices")   # one person's usage: never committed

# Readings are grouped into steps of this clock time, the same clock the tariff schedule uses.
TZ = CONFIG["timezone"]


def device_data(device_id, name):
    """Path of one device's processed readings, e.g. device_data(3, "energy.csv")."""
    os.makedirs(PROCESSED, exist_ok=True)
    return os.path.join(PROCESSED, f"device_{device_id}_{name}")


def device_artifact(device_id, name):
    """Path of one device's model, report or forecast, e.g. device_artifact(3, "model.json")."""
    os.makedirs(DEVICE_DIR, exist_ok=True)
    return os.path.join(DEVICE_DIR, f"device_{device_id}_{name}")


def device_checkpoints(device_id):
    """Folder of one device's fine-tuning checkpoints."""
    return os.path.join(DEVICE_DIR, f"device_{device_id}_checkpoints")


def backend_config():
    """The backend's settings from backend/.env: database, rate, tariff, billing cycle."""
    from app.config import Config

    return Config
