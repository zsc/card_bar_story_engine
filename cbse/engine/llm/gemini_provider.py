from __future__ import annotations

import os
from typing import Any

import httpx

from cbse.engine.llm.base import LLMClient


class GeminiProvider(LLMClient):
    def __init__(
        self,
        model: str,
        temperature: float,
        max_output_tokens: int,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("GEMINI_API_KEY")
        if not self.api_key:
            raise RuntimeError("GEMINI_API_KEY is not set")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = base_url or "https://generativelanguage.googleapis.com/v1beta"

    def complete(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/models/{self.model}:generateContent"
        text = "\n".join(f"{m['role']}: {m['content']}" for m in messages)
        payload: dict[str, Any] = {
            "contents": [{"role": "user", "parts": [{"text": text}]}],
            "generationConfig": {
                "temperature": self.temperature,
                "maxOutputTokens": self.max_output_tokens,
            },
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, params={"key": self.api_key}, json=payload)
            response.raise_for_status()
            data = response.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("No candidates returned from Gemini")
        parts = candidates[0].get("content", {}).get("parts", [])
        if not parts:
            raise RuntimeError("Empty Gemini response")
        return parts[0].get("text", "")
