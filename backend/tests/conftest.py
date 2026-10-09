import time
from datetime import date, datetime, timedelta

import pytest

from app.services import storage


def seed_readings(db, days=30):
    """A month of device readings: llama3:70b on Ollama for about 4 hours a day at 280 W, used a
    little more each day, plus an hour a day loaded but idle. One reading per day, through today."""
    conn = storage.connect(db)
    today = date.today()
    for i in range(days - 1, -1, -1):
        day = today - timedelta(days=i)
        ts = min(datetime.combine(day, datetime.min.time()).timestamp() + 6 * 3600, time.time())
        hours = 4 * (1 + (days - i) * 0.01)
        working = {"app": "Ollama", "model": "Ollama · llama3:70b", "kind": "local", "cpu_percent": 400,
                   "rss_mb": 40_000, "watts": 280}
        storage.save_sample(conn, ts, hours * 3600, 60, 90, 300, None, [working])
        idle = {**working, "cpu_percent": 0, "watts": 9}
        storage.save_sample(conn, ts + 1, 3600, 2, 0, 20, None, [idle])
    conn.close()


@pytest.fixture
def seeded_db(tmp_path):
    db = str(tmp_path / "test.db")
    seed_readings(db)
    return db
