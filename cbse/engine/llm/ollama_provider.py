from __future__ import annotations

import os
from typing import Any

import httpx

from cbse.engine.llm.base import LLMClient


class OllamaProvider(LLMClient):
    def __init__(
        self,
        model: str,
        temperature: float,
        max_output_tokens: int,
        base_url: str | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    def complete(self, messages: list[dict[str, str]]) -> str:
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": "json",
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
            },
        }
        with httpx.Client(timeout=120.0) as client:
            response = client.post(url, json=payload)
            response.raise_for_status()
            data = response.json()
        message = data.get("message", {})
        return message.get("content", "")
