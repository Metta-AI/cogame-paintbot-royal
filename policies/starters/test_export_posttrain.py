"""Whole local games become seed-separated Metta examples."""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent / "common"))

from export_posttrain import export  # noqa: E402
from training_capture import TrainingCapture  # noqa: E402


def test_export_keeps_whole_seeds_together(tmp_path, monkeypatch):
    runs = []
    monkeypatch.setenv("POC_SOURCE_REVISION", "source-head")
    for seed in (679964, 679965):
        run = tmp_path / str(seed)
        run.mkdir()
        (run / "config.json").write_text(json.dumps({"seed": seed}))
        (run / "results.json").write_text(json.dumps({"scores": [seed, 0]}))
        for slot in (0, 1):
            target = run / f"policy_artifact_{slot}.zip"
            monkeypatch.setenv("COWORLD_PLAYER_ARTIFACT_UPLOAD_URL", target.as_uri())
            capture = TrainingCapture(slot, "canned-cautious")
            capture.record("playbook", f"seat {slot}", {"call": {"entries": []}}, 42)
            capture.upload()
        runs.append(run)
    output = tmp_path / "dataset"
    manifest = export(runs, output, "canned-cautious", "source-head")
    assert manifest["train_examples"] == manifest["validation_examples"] == 2
    train = [json.loads(line) for line in (output / "train.jsonl").read_text().splitlines()]
    validation = [json.loads(line) for line in (output / "validation.jsonl").read_text().splitlines()]
    assert {row["seed"] for row in train} == {"paintbot-royal-679964"}
    assert {row["seed"] for row in validation} == {"paintbot-royal-679965"}
    assert output.stat().st_mode & 0o777 == 0o700
    assert all(path.stat().st_mode & 0o777 == 0o600 for path in output.iterdir())
