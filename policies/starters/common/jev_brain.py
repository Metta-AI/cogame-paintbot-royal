"""Jev chooses a starter play call through the ordinary player policy seam."""

from __future__ import annotations

import json
import math
import os
import urllib.request


class JevChoiceBrain:
    def __init__(self, persona, prompt: str) -> None:
        self.persona = persona
        self.prompt = prompt
        self.name = "jev"
        self.calls = 0

        sidecar = os.environ.get("AWS_ENDPOINT_URL_BEDROCK_RUNTIME", "").strip()
        capture = os.environ.get("METTA_CAPTURE_URL", "").strip()
        if sidecar:
            self.endpoint = sidecar
            self.model = "typesafe/jev-1.13"
            self.key = ""
        elif capture:
            self.endpoint = capture
            self.model = os.environ.get("METTA_CAPTURE_MODEL", "jev-latest")
            self.key = os.environ["METTA_CAPTURE_KEY"]
        else:
            self.endpoint = os.environ.get("TYPESAFE_BASE_URL", "https://api.typesafe.ai")
            self.model = os.environ.get("TYPESAFE_DEFAULT_MODEL", "jev-latest")
            self.key = os.environ["TYPESAFE_API_KEY"]

    def decide(self, summary: str) -> dict:
        choices = self.persona.canned_turns
        criteria = {
            str(index): json.dumps(choice, sort_keys=True)
            for index, choice in enumerate(choices)
        }
        body = json.dumps({
            "model": self.model,
            "state": {"policy": self.prompt, "summary": summary},
            "questions": {"action": {"type": "choice",
                                     "instructions": "Choose one legal play call.",
                                     "criteria": criteria}},
        }).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.key:
            headers["Authorization"] = "Bearer " + self.key
        request = urllib.request.Request(
            self.endpoint.rstrip("/") + "/v1/systemone", body, headers,
            method="POST")
        with urllib.request.urlopen(request, timeout=10) as response:
            answer = json.load(response)["answers"]["action"]
        if answer["type"] != "choice" or len(answer["probabilities"]) != len(choices):
            raise ValueError("Jev returned the wrong play-call catalog")
        probabilities = [answer["probabilities"][str(i)] for i in range(len(choices))]
        if (any(not isinstance(p, (int, float)) or not math.isfinite(p)
                or p < 0 or p > 1 for p in probabilities)
                or abs(sum(probabilities) - 1) > len(choices) * 0.005 + 1e-6):
            raise ValueError("Jev returned invalid play-call probabilities")
        self.calls += 1
        return json.loads(json.dumps(choices[max(range(len(choices)),
                                             key=probabilities.__getitem__)]))
