import json
import os

import pytest

from wattcast import backtest, checkpoint, config, model, pipeline, settings

SMALL = model.Spec((1, 0, 0), (1, 0, 0, 24))
OTHER = model.Spec((1, 0, 0), (0, 0, 0, 0))


@pytest.fixture
def fits(monkeypatch):
    """Counts the real fits a run makes."""
    calls = []
    real = model.fit

    def counting(y, spec, **kw):
        calls.append(spec.label)
        return real(y, spec, **kw)

    monkeypatch.setattr(model, "fit", counting)
    monkeypatch.setattr(backtest, "fit", counting)
    return calls


def test_pretrain_resumes_from_checkpoints(wh, fits):
    log = []
    first = pipeline.pretrain(wh, [SMALL, OTHER], folds=2, log=log.append)
    assert len(fits) == 3  # two backtests and the final fit of the best
    assert first["run"]["checkpoints"] == {"folder": "checkpoints", "fitted": 3, "from_checkpoint": 0}
    saved = sorted(os.listdir(settings.LUZON_CHECKPOINTS))
    assert "config.json" in saved and len(saved) == 4

    again = pipeline.pretrain(wh, [SMALL, OTHER], folds=2, log=log.append)
    assert len(fits) == 3  # nothing fitted again
    assert again["run"]["checkpoints"]["from_checkpoint"] == 3 and "(from checkpoint)" in log[-2]
    assert json.dumps(again["ranking"]) == json.dumps(first["ranking"])  # same result as the first run
    assert again["model"]["params"] == first["model"]["params"]


def test_an_interrupted_run_keeps_what_it_finished(wh, fits, monkeypatch):
    real = backtest.evaluate

    def interrupted(y, spec, origins, **kw):
        if spec == OTHER:
            raise KeyboardInterrupt  # the user stops the run during the second candidate
        return real(y, spec, origins, **kw)

    monkeypatch.setattr(backtest, "evaluate", interrupted)
    with pytest.raises(KeyboardInterrupt):
        pipeline.pretrain(wh, [SMALL, OTHER], folds=2, log=lambda *_: None)
    monkeypatch.setattr(backtest, "evaluate", real)
    done = len(fits)
    result = pipeline.pretrain(wh, [SMALL, OTHER], folds=2, log=lambda *_: None)
    assert (result["run"]["checkpoints"]["fitted"], result["run"]["checkpoints"]["from_checkpoint"]) == (2, 1)
    assert len(fits) == done + 2  # only the second candidate and the final fit


def test_checkpoints_are_not_reused_for_other_data_or_when_fresh(wh, fits):
    pipeline.pretrain(wh, [SMALL], folds=2, log=lambda *_: None)
    changed = wh.copy()
    changed.iloc[5] += 1.0
    pipeline.pretrain(changed, [SMALL], folds=2, log=lambda *_: None)
    assert len(fits) == 4  # different data: fitted again
    pipeline.pretrain(changed, [SMALL], folds=2, ckpt=pipeline.luzon_checkpoints(fresh=True), log=lambda *_: None)
    assert len(fits) == 6  # --fresh: fitted again, and the checkpoints replaced


def test_finetune_checkpoints_each_agent_and_records_the_run(agents, fits):
    from types import SimpleNamespace

    bill_cfg = SimpleNamespace(ELECTRICITY_RATE=12.0, TARIFF="flat", POP_PEAK_RATE=0, POP_OFFPEAK_RATE=0,
                               BASELINE_BILL=1500.0, BILLING_CYCLE_START_DAY=1, DATABASE="mysql://user:secret@host/db")
    saved = pipeline.finetune(agents, 7, [(SMALL, None)], folds=2, top=1, bill_cfg=bill_cfg, log=lambda *_: None)
    first = len(fits)
    run = saved["run"]
    assert run["checkpoints"]["fitted"] == first == 6  # per agent: routine only, one structure, the final fit
    assert run["config"] == config.CONFIG and run["bill_settings"]["baseline_bill"] == 1500.0
    assert run["agents"] == ["Ollama", "Claude Code"] and set(run["versions"]) >= {"statsmodels", "pandas", "python"}
    assert "secret" not in json.dumps(saved)  # no database credentials in what's saved
    folder = settings.device_checkpoints(7)
    with open(os.path.join(folder, "config.json")) as f:
        assert json.load(f)["config"]["device"]["min_hours"] == 72

    again = pipeline.finetune(agents, 7, [(SMALL, None)], folds=2, top=1, bill_cfg=bill_cfg, log=lambda *_: None)
    assert len(fits) == first and again["run"]["checkpoints"]["from_checkpoint"] == 6
    assert again["total"] == saved["total"]
    assert {a: v["chosen"] for a, v in again["agents"].items()} == {a: v["chosen"] for a, v in saved["agents"].items()}


def test_run_record_gives_the_checkpoint_folder_relative_to_the_training_folder():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    inside = checkpoint.Checkpoints(os.path.join(root, "artifacts", "luzon", "checkpoints"))
    assert inside.summary()["folder"] == os.path.join("artifacts", "luzon", "checkpoints")  # no home folder path


def test_a_half_written_checkpoint_is_ignored(tmp_path):
    ckpt = checkpoint.Checkpoints(str(tmp_path))
    ckpt.save("a", "key1", {"value": 1})
    assert ckpt.load("a", "key1")["value"] == 1 and ckpt.load("a", "other-key") is None
    (tmp_path / "b.json").write_text('{"key": "key1", "val')  # killed while writing
    assert ckpt.load("b", "key1") is None
    off = checkpoint.Checkpoints(str(tmp_path / "off"), enabled=False)
    off.save("a", "k", {})
    assert not (tmp_path / "off").exists() and off.load("a", "k") is None


def test_config_file_overrides_defaults_and_rejects_typos(tmp_path):
    assert config.load() == config.DEFAULTS  # the config.json in the folder spells out the defaults
    path = tmp_path / "config.json"
    path.write_text(json.dumps({"luzon": {"days": 30}}))
    loaded = config.load(str(path))
    assert loaded["luzon"]["days"] == 30 and loaded["luzon"]["folds"] == 7 and loaded["device"]["gaps"] == "day"
    path.write_text(json.dumps({"luzon": {"dayz": 30}}))
    with pytest.raises(ValueError, match="luzon.dayz"):
        config.load(str(path))
