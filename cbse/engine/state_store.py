from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from cbse.engine.models import Choice, TurnRecord
from cbse.engine.utils import clone_state, deep_get, is_number


@dataclass
class DeltaInfo:
    changed: bool
    summary: str = ""
    numeric_delta: float | None = None


@dataclass
class StateStore:
    state: dict[str, Any]
    history: list[TurnRecord] = field(default_factory=list)
    memory_summary: str = ""
    last_state: dict[str, Any] = field(default_factory=dict)
    last_deltas: dict[str, DeltaInfo] = field(default_factory=dict)
    last_choices: list[Choice] = field(default_factory=list)
    triggered_triggers: set[str] = field(default_factory=set)

    def snapshot(self) -> dict[str, Any]:
        return clone_state(self.state)

    def update_last_state(self) -> None:
        self.last_state = clone_state(self.state)

    def compute_deltas(self) -> dict[str, DeltaInfo]:
        deltas: dict[str, DeltaInfo] = {}
        if not self.last_state:
            self.last_deltas = deltas
            return deltas

        for key, current in self.state.items():
            if key not in self.last_state:
                deltas[key] = DeltaInfo(changed=True, summary="new")
                continue
            previous = self.last_state[key]
            if is_number(current) and is_number(previous):
                diff = float(current) - float(previous)
                if diff != 0:
                    deltas[key] = DeltaInfo(changed=True, summary=f"{diff:+.0f}", numeric_delta=diff)
                else:
                    deltas[key] = DeltaInfo(changed=False, summary="")
            elif isinstance(current, list) and isinstance(previous, list):
                if current != previous:
                    deltas[key] = DeltaInfo(changed=True, summary="updated")
                else:
                    deltas[key] = DeltaInfo(changed=False, summary="")
            elif isinstance(current, dict) and isinstance(previous, dict):
                if current != previous:
                    deltas[key] = DeltaInfo(changed=True, summary="updated")
                else:
                    deltas[key] = DeltaInfo(changed=False, summary="")
            else:
                if current != previous:
                    deltas[key] = DeltaInfo(changed=True, summary=f"{previous} → {current}")
                else:
                    deltas[key] = DeltaInfo(changed=False, summary="")

        self.last_deltas = deltas
        return deltas

    def get_delta(self, var_id: str) -> DeltaInfo | None:
        return self.last_deltas.get(var_id)

    def get_value(self, path: str) -> Any:
        return deep_get(self.state, path)
