"""A trained policy receives the same messages the exporter records."""

import json

from posttrain_brain import PosttrainBrain


def test_posttrained_policy_uses_the_ordinary_decision_shape():
    def generate(messages, deadline):
        assert deadline > 0
        assert messages == [
            {"role": "system", "content": "visible playbook"},
            {"role": "user", "content": "visible match"},
        ]
        return json.dumps({"chat": "go", "call": {"entries": [{"play": "edge_ride"}]}})

    brain = PosttrainBrain(generate, "visible playbook")
    assert brain.decide("visible match")["call"]["entries"][0]["play"] == "edge_ride"
    assert brain.calls == 1
