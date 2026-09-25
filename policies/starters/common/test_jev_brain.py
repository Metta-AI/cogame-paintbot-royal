"""Jev uses the same play-call decisions as an ordinary starter policy."""

import io
import json
from types import SimpleNamespace

import jev_brain
import pytest


def test_jev_selects_a_player_policy_decision(monkeypatch):
    choices = [
        {"chat": "hold", "call": {"entries": [{"play": "edge_ride"}]}},
        {"chat": "hunt", "call": {"entries": [{"play": "jackal"}]}},
    ]
    monkeypatch.setenv("METTA_CAPTURE_URL", "http://local-jev")
    monkeypatch.setenv("METTA_CAPTURE_KEY", "local-test")

    def reply(request, timeout):
        assert timeout == 10
        assert request.full_url == "http://local-jev/v1/systemone"
        assert request.get_header("Authorization") == "Bearer local-test"
        body = json.loads(request.data)
        assert body["state"] == {"policy": "visible playbook", "summary": "visible match"}
        assert [json.loads(item) for item in body["questions"]["action"]["criteria"].values()] == choices
        return io.BytesIO(json.dumps({
            "answers": {"action": {"type": "choice", "probabilities": {"0": 0.1, "1": 0.9}}}
        }).encode())

    monkeypatch.setattr(jev_brain.urllib.request, "urlopen", reply)
    engine = jev_brain.JevChoiceBrain(SimpleNamespace(canned_turns=choices), "visible playbook")
    chosen = engine.decide("visible match")
    assert chosen == choices[1]
    assert chosen is not choices[1]
    assert engine.calls == 1


def test_jev_rejects_nonfinite_policy_weights(monkeypatch):
    monkeypatch.setenv("METTA_CAPTURE_URL", "http://local-jev")
    monkeypatch.setenv("METTA_CAPTURE_KEY", "local-test")
    monkeypatch.setattr(
        jev_brain.urllib.request, "urlopen",
        lambda request, timeout: io.BytesIO(
            b'{"answers":{"action":{"type":"choice","probabilities":{"0":NaN}}}}'
        ),
    )
    engine = jev_brain.JevChoiceBrain(SimpleNamespace(canned_turns=[{"call": {"entries": []}}]), "p")
    with pytest.raises(ValueError, match="invalid play-call probabilities"):
        engine.decide("visible match")


def test_hosted_jev_uses_pinned_model_and_player_pod_attribution(monkeypatch):
    monkeypatch.setenv("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", "http://sidecar")
    monkeypatch.setenv("METTA_CAPTURE_URL", "http://local-jev")

    def reply(request, timeout):
        assert request.full_url == "http://sidecar/v1/systemone"
        assert request.get_header("Authorization") is None
        assert request.get_header("X-Coworld-Player-Slot") is None
        assert json.loads(request.data)["model"] == "typesafe/jev-1.13"
        return io.BytesIO(
            b'{"answers":{"action":{"type":"choice","probabilities":{"0":1}}}}'
        )

    monkeypatch.setattr(jev_brain.urllib.request, "urlopen", reply)
    engine = jev_brain.JevChoiceBrain(SimpleNamespace(canned_turns=[{"call": {"entries": []}}]), "p")
    engine.decide("visible match")
