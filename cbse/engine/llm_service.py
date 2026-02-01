from __future__ import annotations

from dataclasses import dataclass

from cbse.engine.llm.base import LLMClient
from cbse.engine.models import Choice, EndState, Event, LLMOutput, StateUpdateOp
from cbse.engine.schema_validator import SchemaError, SchemaValidator


@dataclass
class LLMResult:
    output: LLMOutput
    raw: str
    used_fallback: bool
    error: str | None = None


class LLMService:
    def __init__(
        self,
        client: LLMClient,
        validator: SchemaValidator,
        max_retries: int = 2,
    ) -> None:
        self.client = client
        self.validator = validator
        self.max_retries = max_retries

    def generate(self, messages: list[dict[str, str]]) -> LLMResult:
        try:
            raw = self.client.complete(messages)
            output = self.validator.parse(raw)
            return LLMResult(output=output, raw=raw, used_fallback=False)
        except Exception as exc:
            raw = getattr(exc, "raw", "") or ""
            error = str(exc)

        for _ in range(self.max_retries):
            repair_messages = self._repair_messages(error, raw)
            try:
                raw = self.client.complete(repair_messages)
                output = self.validator.parse(raw)
                return LLMResult(output=output, raw=raw, used_fallback=False)
            except Exception as exc:
                error = str(exc)

        fallback = self._fallback_output()
        return LLMResult(output=fallback, raw=raw, used_fallback=True, error=error)

    def _repair_messages(self, error: str, raw: str) -> list[dict[str, str]]:
        return [
            {
                "role": "system",
                "content": "You are a JSON repair engine. Output ONLY valid JSON that matches the schema.",
            },
            {
                "role": "user",
                "content": f"Fix the JSON. Error: {error}\nRaw:\n{raw}",
            },
        ]

    def _fallback_output(self) -> LLMOutput:
        return LLMOutput(
            narrative_markdown="System: LLM output invalid. Choose an action.",
            choices=[
                Choice(
                    id="retry",
                    label="Retry",
                    hint="Try generating again.",
                    risk="low",
                    tags=["system"],
                ),
                Choice(
                    id="rollback",
                    label="Rollback",
                    hint="Keep current state and wait.",
                    risk="low",
                    tags=["system"],
                ),
                Choice(
                    id="exit",
                    label="Exit",
                    hint="Quit the game.",
                    risk="low",
                    tags=["system"],
                ),
            ],
            state_updates=[],
            new_facts=[],
            events=[Event(type="error", message="LLM output invalid")],
            end=EndState(is_game_over=False, ending_id="", reason=""),
        )
