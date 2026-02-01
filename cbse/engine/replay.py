from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_replay_inputs(path: Path) -> list[str]:
    if not path.exists():
        raise FileNotFoundError(path)
    suffix = path.suffix.lower()
    if suffix in {".json", ".jsonl"}:
        return _load_json_like(path)
    if suffix in {".txt", ".log"}:
        return _load_text_lines(path)
    # Fallback: try JSON then text
    try:
        return _load_json_like(path)
    except Exception:
        return _load_text_lines(path)


def _load_json_like(path: Path) -> list[str]:
    text = path.read_text(encoding="utf-8").strip()
    if not text:
        return []
    if path.suffix.lower() == ".jsonl":
        return _load_jsonl(text)
    if text.startswith("{") or text.startswith("["):
        data = json.loads(text)
        return _normalize_inputs(data)
    return _load_jsonl(text)


def _load_jsonl(text: str) -> list[str]:
    inputs: list[str] = []
    for line in text.splitlines():
        line = line.strip()
        if not line:
            continue
        if line.startswith("#"):
            continue
        if line.startswith("{") or line.startswith("["):
            data = json.loads(line)
            inputs.extend(_normalize_inputs(data))
        else:
            inputs.append(line)
    return inputs


def _load_text_lines(path: Path) -> list[str]:
    inputs: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        inputs.append(line)
    return inputs


def _normalize_inputs(data: Any) -> list[str]:
    if isinstance(data, str):
        return [data]
    if isinstance(data, list):
        return [str(item) for item in data]
    if isinstance(data, dict):
        if "inputs" in data and isinstance(data["inputs"], list):
            return [str(item) for item in data["inputs"]]
        if "input" in data:
            return [str(data["input"])]
    raise ValueError("Unsupported replay format")
