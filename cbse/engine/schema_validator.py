from __future__ import annotations

import json
from typing import Any

from pydantic import ValidationError

from cbse.engine.models import Choice, EndState, Event, LLMOutput, StateUpdateOp


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

    def coerce(self, text: str) -> LLMOutput:
        json_text = extract_json(text)
        data = json.loads(json_text)
        if not isinstance(data, dict):
            raise SchemaError("Coerce expects an object")

        narrative = data.get("narrative_markdown")
        if not isinstance(narrative, str):
            narrative = data.get("narrative") if isinstance(data.get("narrative"), str) else None
        if not isinstance(narrative, str):
            narrative = data.get("story") if isinstance(data.get("story"), str) else None
        if not isinstance(narrative, str):
            narrative = "你整理了一下思绪，夜色仍在推进。"

        choices_raw = data.get("choices")
        choices: list[Choice] = []
        if isinstance(choices_raw, list):
            for idx, item in enumerate(choices_raw):
                if isinstance(item, str):
                    label = item
                    choice_id = f"choice_{idx+1}"
                    choices.append(Choice(id=choice_id, label=label, hint="", risk="low", tags=[]))
                elif isinstance(item, dict):
                    label = item.get("label") or item.get("text") or item.get("title") or f"选择{idx+1}"
                    if not isinstance(label, str):
                        label = f"选择{idx+1}"
                    choice_id = item.get("id") or f"choice_{idx+1}"
                    hint = item.get("hint") if isinstance(item.get("hint"), str) else ""
                    risk = item.get("risk") if item.get("risk") in {"low", "medium", "high"} else "low"
                    tags = item.get("tags") if isinstance(item.get("tags"), list) else []
                    choices.append(Choice(id=str(choice_id), label=label, hint=hint, risk=risk, tags=tags))

        if len(choices) < 3:
            defaults = [
                Choice(id="observe", label="观察周围动静", hint="先稳住局面。", risk="low", tags=["stealth"]),
                Choice(id="ask", label="追问细节", hint="可能拿到线索。", risk="medium", tags=["investigate"]),
                Choice(id="move", label="转移地点", hint="推进时间与情势。", risk="medium", tags=["travel"]),
            ]
            choices.extend(defaults[len(choices) : 3])
        if len(choices) > 6:
            choices = choices[:6]

        updates_raw = data.get("state_updates")
        updates: list[StateUpdateOp] = []
        if isinstance(updates_raw, list):
            for item in updates_raw:
                if not isinstance(item, dict):
                    continue
                op = item.get("op")
                path = item.get("path")
                if op not in {"set", "inc", "dec", "push", "remove", "toggle"}:
                    continue
                if not isinstance(path, str):
                    continue
                updates.append(
                    StateUpdateOp(
                        op=op,
                        path=path,
                        value=item.get("value"),
                        reason=item.get("reason") if isinstance(item.get("reason"), str) else "",
                    )
                )

        new_facts_raw = data.get("new_facts")
        new_facts = [f for f in new_facts_raw if isinstance(f, str)] if isinstance(new_facts_raw, list) else []

        events_raw = data.get("events")
        events: list[Event] = []
        if isinstance(events_raw, list):
            for item in events_raw:
                if not isinstance(item, dict):
                    continue
                etype = item.get("type") if isinstance(item.get("type"), str) else "info"
                msg = item.get("message") if isinstance(item.get("message"), str) else ""
                if msg:
                    events.append(Event(type=etype, message=msg))

        end_raw = data.get("end")
        if isinstance(end_raw, dict):
            end = EndState(
                is_game_over=bool(end_raw.get("is_game_over", False)),
                ending_id=str(end_raw.get("ending_id", "")),
                reason=str(end_raw.get("reason", "")),
            )
        elif isinstance(end_raw, bool):
            end = EndState(is_game_over=end_raw, ending_id="", reason="")
        else:
            end = EndState()

        events.append(Event(type="coerced_output", message="Coerced invalid LLM JSON into schema."))

        return LLMOutput(
            narrative_markdown=narrative,
            choices=choices,
            state_updates=updates,
            new_facts=new_facts,
            events=events,
            end=end,
        )
