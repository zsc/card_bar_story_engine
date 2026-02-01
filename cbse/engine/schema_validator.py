from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from cbse.engine.models import LLMOutput


class SchemaError(Exception):
    pass


def extract_json(text: str) -> str:
    text = text.strip()
    if text.startswith("{") and text.endswith("}"):
        return text
    start = text.find("{")
    end = text.rfind("}")
    if start != -1 and end != -1 and end > start:
        return text[start : end + 1]
    raise SchemaError("No JSON object found")


class SchemaValidator:
    def parse(self, text: str) -> LLMOutput:
        try:
            json_text = extract_json(text)
            data = json.loads(json_text)
            return LLMOutput.model_validate(data)
        except (json.JSONDecodeError, ValidationError, SchemaError) as exc:
            raise SchemaError(str(exc)) from exc
