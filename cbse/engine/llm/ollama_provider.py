from __future__ import annotations

import os
from typing import Any

import httpx

from cbse.engine.llm.base import LLMClient


class OllamaProviderError(RuntimeError):
    def __init__(self, message: str, raw: str = "") -> None:
        super().__init__(message)
        self.raw = raw


class OllamaProvider(LLMClient):
    def __init__(
        self,
        model: str,
        temperature: float,
        max_output_tokens: int,
        base_url: str | None = None,
        json_schema: dict | None = None,
        timeout: float | None = None,
        format_mode: str | None = None,
        num_ctx: int | None = None,
    ) -> None:
        self.model = model
        self.temperature = temperature
        self.max_output_tokens = max_output_tokens
        self.base_url = base_url or os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
        self.json_schema = json_schema
        if timeout is None:
            timeout_env = os.getenv("CBSE_OLLAMA_TIMEOUT") or os.getenv("OLLAMA_TIMEOUT")
            timeout = float(timeout_env) if timeout_env else 120.0
        self.timeout = timeout
        if format_mode is None:
            format_mode = os.getenv("CBSE_OLLAMA_FORMAT") or os.getenv("OLLAMA_FORMAT") or "json"
        self.format_mode = format_mode
        if num_ctx is None:
            num_ctx_env = os.getenv("CBSE_OLLAMA_NUM_CTX") or os.getenv("OLLAMA_NUM_CTX")
            num_ctx = int(num_ctx_env) if num_ctx_env else None
        self.num_ctx = num_ctx

    def complete(self, messages: list[dict[str, str]]) -> str:
        if self.format_mode == "json_schema":
            if not self.json_schema:
                raise OllamaProviderError("json_schema format requires a schema.")
            content, raw = self._request(messages, fmt=self.json_schema)
            if not content.strip():
                raise OllamaProviderError("Ollama returned empty content for json_schema format.", raw=raw)
            return content

        content, raw = self._request(messages, fmt="json")
        if not content.strip():
            raise OllamaProviderError("Ollama returned empty content.", raw=raw)
        return content

    def _request(self, messages: list[dict[str, str]], fmt: Any) -> tuple[str, str]:
        url = f"{self.base_url}/api/chat"
        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": fmt,
            "options": {
                "temperature": self.temperature,
                "num_predict": self.max_output_tokens,
            },
        }
        if self.num_ctx is not None:
            payload["options"]["num_ctx"] = self.num_ctx
        with httpx.Client(timeout=self.timeout) as client:
            response = client.post(url, json=payload)
            response_text = response.text
            try:
                response.raise_for_status()
            except httpx.HTTPStatusError as exc:
                raise OllamaProviderError(f"Ollama HTTP error: {exc}", raw=response_text) from exc
            try:
                data = response.json()
            except ValueError as exc:
                raise OllamaProviderError("Ollama returned non-JSON response.", raw=response_text) from exc
        if isinstance(data, dict) and data.get("error"):
            raise OllamaProviderError(f"Ollama error: {data['error']}", raw=response_text)
        message = data.get("message", {})
        return str(message.get("content", "")), response_text
