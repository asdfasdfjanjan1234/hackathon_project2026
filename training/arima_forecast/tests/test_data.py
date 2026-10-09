import io
import zipfile
from datetime import datetime
from zoneinfo import ZoneInfo

import pandas as pd
import pytest

from app.services import storage
from wattcast import iemop, readings

HEADER = ("RUN_TIME,MKT_TYPE,TIME_INTERVAL,REGION_NAME,COMMODITY_TYPE,MKT_REQT,LOAD_BID,LOAD_CURTAILED,"
          "LOSSES,GENERATION,MKT_IMPORT,MKT_EXPORT,\n")


def _row(end, region, commodity, mw):
    # IEMOP's format: no leading zeros ("9/15/2026 1:05:00 AM"), and the interval ending at midnight
    # as a bare date. Built by hand: strftime's no-padding codes differ between Windows and macOS/Linux.
    t = f"{end.month}/{end.day}/{end.year}"
    if not end.hour == end.minute == 0:
        t += f" {end.hour % 12 or 12}:{end.minute:02d}:00 {'AM' if end.hour < 12 else 'PM'}"
    return f"{t},RTD,{t},{region},{commodity},{mw},0,0,0,{mw},0,0,\n"


def test_hourly_demand_averages_intervals_into_the_hour_they_end_in(tmp_path):
    lines = [HEADER]
    start = pd.Timestamp("2026-09-14 23:00")
    for i in range(1, 37):  # intervals ending 11:05 PM ... 2:00 AM: three full hours
        end = start + pd.Timedelta(minutes=5 * i)
        lines.append(_row(end, "CLUZ", "En", 8000 if i <= 12 else 9000 if i <= 24 else 10000))
        lines.append(_row(end, "CLUZ", "Dr", 600))   # reserve rows are ignored
        lines.append(_row(end, "CVIS", "En", 1800))  # other regions too
    for i in range(37, 42):  # only 5 intervals of the 2 AM hour
        lines.append(_row(start + pd.Timedelta(minutes=5 * i), "CLUZ", "En", 11000))
    lines.append("EOF\n")
    (tmp_path / "RTDREG_20260915.csv").write_text("".join(lines))

    hourly = iemop.hourly_demand(str(tmp_path))
    assert hourly[pd.Timestamp("2026-09-14 23:00")] == 8000  # includes the interval ending at midnight
    assert hourly[pd.Timestamp("2026-09-15 00:00")] == 9000
    assert hourly[pd.Timestamp("2026-09-15 01:00")] == 10000
    assert pd.isna(hourly[pd.Timestamp("2026-09-15 02:00")])


def test_save_files_keeps_only_daily_files_by_name(tmp_path):
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as z:
        z.writestr("RTDREG_20260101.csv", "a")
        z.writestr("../RTDREG_20260102.csv", "b")
        z.writestr("../../evil.py", "c")
    assert sorted(iemop.save_files(buf.getvalue(), str(tmp_path))) == ["RTDREG_20260101.csv", "RTDREG_20260102.csv"]
    assert sorted(p.name for p in tmp_path.iterdir()) == ["RTDREG_20260101.csv", "RTDREG_20260102.csv"]
    assert iemop.save_files(buf.getvalue(), str(tmp_path)) == []  # already saved


def _readings(tmp_path):
    """Sep 15: the reader runs all of the 9 AM hour with no AI, then Ollama at 30 W for 30 minutes of
    the 10 AM hour and Claude Code at 2 W for 10 minutes of the 11 AM hour. Nothing on Sep 16.
    Sep 17: Claude Code at 2 W plus its tool runs at 1 W for the whole 9 AM hour."""
    conn = storage.connect(str(tmp_path / "r.db"))
    device = storage.register_device(conn, {"machine_id": "m1", "hostname": "test"})
    manila = ZoneInfo("Asia/Manila")
    ollama = {"app": "Ollama", "model": "Ollama · llama3:8b", "kind": "local", "cpu_percent": 300, "rss_mb": 5000, "watts": 30}
    claude = {"app": "Claude Code", "model": "Claude Code · claude-opus", "kind": "client", "cpu_percent": 20, "rss_mb": 400, "watts": 2}
    tools = {**claude, "model": "Claude Code · tool runs", "watts": 1}
    t0 = datetime(2026, 9, 15, 10, tzinfo=manila).timestamp()
    for i in range(6):
        storage.save_sample(conn, t0 - 3600 + i * 600, 600, 5, 0, 10, None, [], device_id=device)
    for i in range(3):
        storage.save_sample(conn, t0 + i * 600, 600, 50, 40, 40, None, [ollama], device_id=device)
    storage.save_sample(conn, t0 + 3600, 600, 5, 0, 10, None, [claude], device_id=device)
    t2 = datetime(2026, 9, 17, 9, tzinfo=manila).timestamp()
    for i in range(6):
        storage.save_sample(conn, t2 + i * 600, 600, 5, 0, 10, None, [claude, tools], device_id=device)
    return conn, device


TEN, ELEVEN = pd.Timestamp("2026-09-15 10:00"), pd.Timestamp("2026-09-15 11:00")
NOON, NEXT_DAY, LAST = pd.Timestamp("2026-09-15 12:00"), pd.Timestamp("2026-09-16 12:00"), pd.Timestamp("2026-09-17 09:00")


def test_hourly_ai_energy_counts_gaps_as_no_use_only_on_days_the_reader_ran(tmp_path):
    conn, device = _readings(tmp_path)
    hourly, by_app = readings.hourly_ai_energy(conn, device)  # gaps="day"
    conn.close()
    assert hourly.loc[TEN, "measured_h"] == pytest.approx(0.5)
    assert hourly.loc[TEN, "wh"] == pytest.approx(15)          # 30 W for half an hour, as measured
    assert hourly.loc[ELEVEN, "wh"] == pytest.approx(2 / 6)    # 2 W for 10 minutes
    assert hourly.loc[NOON, "wh"] == 0                          # the reader ran that day: no AI use
    assert pd.isna(hourly.loc[NEXT_DAY, "wh"])                  # no readings that day: unknown
    assert hourly.loc[LAST, "wh"] == pytest.approx(3)           # the agent and its tool runs
    assert set(by_app["app"]) == {"Ollama", "Claude Code"}
    assert by_app[by_app["hour"] == LAST]["wh"].sum() == pytest.approx(3)


def test_other_gap_rules(tmp_path):
    conn, device = _readings(tmp_path)
    missing, _ = readings.hourly_ai_energy(conn, device, gaps="missing")
    zero, _ = readings.hourly_ai_energy(conn, device, gaps="zero")
    conn.close()
    assert missing.loc[TEN, "wh"] == pytest.approx(30)  # half the hour measured, scaled to the full hour
    assert pd.isna(missing.loc[ELEVEN, "wh"]) and pd.isna(missing.loc[NOON, "wh"])  # under half measured
    assert zero.loc[NEXT_DAY, "wh"] == 0
    with pytest.raises(ValueError):
        readings.hourly_ai_energy(None, device, gaps="guess")


def test_agent_series_one_column_per_agent_small_ones_together():
    index = pd.date_range("2026-09-14", periods=72, freq="h")
    hourly = pd.DataFrame({"measured_h": 1.0, "ai_wh": 0.0, "scale": 1.0}, index=index)
    hourly.loc[index[-24:], "scale"] = float("nan")  # the last day is unknown
    rows = ([{"hour": h, "app": "Ollama", "name": "Ollama · llama3:8b", "kind": "local", "wh": 20.0} for h in index[:30]]
            + [{"hour": h, "app": "Claude Code", "name": "Claude Code · tool runs", "kind": "client", "wh": 1.0} for h in index]
            + [{"hour": h, "app": "Claude Code", "name": "Claude Code · opus", "kind": "client", "wh": 2.0} for h in index]
            + [{"hour": h, "app": "GitHub Copilot", "name": "GitHub Copilot", "kind": "client", "wh": 0.001} for h in index]
            + [{"hour": index[0], "app": "Codex", "name": "Codex", "kind": "client", "wh": 5.0}])
    agents = readings.agent_series(hourly, pd.DataFrame(rows))
    assert list(agents.columns) == ["Ollama", "Claude Code", readings.OTHER]  # biggest first
    assert agents["Claude Code"].iloc[0] == 3                     # its models and tool runs together
    assert agents[readings.OTHER].iloc[0] == pytest.approx(5.001)  # Copilot (tiny) and Codex (one hour)
    assert agents.iloc[-1].isna().all() and agents["Ollama"].iloc[40] == 0
