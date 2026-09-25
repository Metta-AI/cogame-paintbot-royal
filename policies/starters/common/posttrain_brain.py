"""Metta-trained play-call replies through the starter's normal brain seam."""

from __future__ import annotations

import hashlib
import json
import threading
import time
from pathlib import Path
from typing import Callable


class PosttrainBrain:
    def __init__(self, generate: Callable[[list[dict[str, str]], float], str], prompt: str) -> None:
        self.generate = generate
        self.prompt = prompt
        self.name = "metta-posttrain"
        self.calls = 0

    def decide(self, summary: str) -> dict:
        messages = [
            {"role": "system", "content": self.prompt},
            {"role": "user", "content": summary},
        ]
        answer = json.loads(self.generate(messages, time.monotonic() + 30))
        if not isinstance(answer, dict):
            raise ValueError("post-trained policy must return a JSON object")
        self.calls += 1
        return answer


class TransformersGenerator:
    def __init__(self, adapter: Path, device: str = "cpu") -> None:
        import torch
        from peft import PeftModel
        from transformers import AutoModelForCausalLM, AutoTokenizer

        manifest = json.loads((adapter / "training_manifest.json").read_text())
        base = manifest["model"]
        revision = manifest["revision"]
        if Path(base).is_dir():
            digest = hashlib.sha256()
            for path in sorted(path for path in Path(base).rglob("*") if path.is_file()):
                digest.update(str(path.relative_to(base)).encode())
                digest.update(hashlib.sha256(path.read_bytes()).digest())
            if revision != f"local-sha256:{digest.hexdigest()}":
                raise ValueError("base model differs from the training manifest")
            tokenizer = AutoTokenizer.from_pretrained(base)
            network = AutoModelForCausalLM.from_pretrained(base, device_map=device)
        else:
            tokenizer = AutoTokenizer.from_pretrained(base, revision=revision)
            network = AutoModelForCausalLM.from_pretrained(base, revision=revision, device_map=device)
            if network.config._commit_hash != revision:
                raise ValueError("base model revision differs from the training manifest")
        self.tokenizer = tokenizer
        self.network = PeftModel.from_pretrained(network, adapter)
        self.network.eval()
        self.lock = threading.Lock()
        self.torch = torch
        self.max_length = manifest["max_length"]

    def __call__(self, messages: list[dict[str, str]], deadline: float) -> str:
        from transformers import MaxTimeCriteria, StoppingCriteriaList

        with self.lock:
            inputs = self.tokenizer.apply_chat_template(
                messages, tokenize=True, add_generation_prompt=True,
                enable_thinking=False, return_tensors="pt", return_dict=True,
            ).to(self.network.device)
            length = inputs["input_ids"].shape[-1]
            if length > self.max_length:
                raise ValueError(f"player prompt has {length} tokens, above {self.max_length}")
            remaining = deadline - time.monotonic()
            if remaining <= 0:
                raise TimeoutError("no player decision time remains")
            with self.torch.inference_mode():
                generated = self.network.generate(
                    **inputs, do_sample=False, max_new_tokens=768,
                    pad_token_id=self.tokenizer.eos_token_id,
                    stopping_criteria=StoppingCriteriaList([MaxTimeCriteria(max_time=remaining)]),
                )
            return self.tokenizer.decode(generated[0, length:], skip_special_tokens=True)
