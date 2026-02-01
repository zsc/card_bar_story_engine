from __future__ import annotations

import os
from typing import Any

import httpx

from cbse.engine.llm.base import LLMClient


class OpenAIProvider(LLMClient):
    def __init__(
        self,
        model: str,
        temperature: float,
        max_output_tokens: int,
        api_key: str | None = None,
        base_url: str | None = None,
    ) -> None:
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        if not self.api_key:
            raise RuntimeError("OPENAI_API_KEY is not set")
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = base_url or "https://api.openai.com/v1"

    def complete(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/chat/completions"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": self.temperature,
            "max_tokens": self.max_output_tokens,
            "response_format": {"type": "json_object"},
        }
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        with httpx.Client(timeout=60.0) as client:
            response = client.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
        return data["choices"][0]["message"]["content"]
