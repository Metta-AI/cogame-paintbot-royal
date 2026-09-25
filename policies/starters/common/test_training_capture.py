"""Accepted player replies are available through the standard artifact path."""

import json
import zipfile

from training_capture import TrainingCapture


def test_capture_writes_the_player_artifact(tmp_path, monkeypatch):
    target = tmp_path / "policy.zip"
    monkeypatch.setenv("POC_SOURCE_REVISION", "source-head")
    monkeypatch.setenv("COWORLD_PLAYER_ARTIFACT_UPLOAD_URL", target.as_uri())
    capture = TrainingCapture(slot=3, backend="canned-cautious")
    capture.record("visible playbook", "visible seat", {"call": {"entries": []}}, 42)
    assert not target.exists()
    capture.upload()
    with zipfile.ZipFile(target) as archive:
        record = json.loads(archive.read("trajectory.json"))
    assert record["complete"] is True
    assert record["source_revision"] == "source-head"
    assert record["slot"] == 3
    assert record["backend"] == "canned-cautious"
    assert record["decisions"][0]["tick"] == 42
    assert record["decisions"][0]["prompt"][1]["content"] == "visible seat"
