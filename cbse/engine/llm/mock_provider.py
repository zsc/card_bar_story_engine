from __future__ import annotations

import json
import random
from typing import Any

from cbse.engine.llm.base import LLMClient


class MockProvider(LLMClient):
    def __init__(self, variable_ids: set[str], location_values: list[str] | None = None) -> None:
        self.variable_ids = variable_ids
        self.location_values = location_values or []
        self.turn_index = 0
        self.rng = random.Random(42)

    def complete(self, messages: list[dict[str, str]]) -> str:
        self.turn_index += 1
        idx = self.turn_index

        narrative = (
            f"The harbor wind tastes of salt; you press on at turn {idx}.\n\n"
            "Clues are scarce, but every door in the city feels half-open."
        )

        choices = [
            {
                "id": "press_lead",
                "label": "Press the lead for more detail",
                "hint": "May add clues, may provoke someone.",
                "risk": "medium",
                "tags": ["investigate"],
            },
            {
                "id": "move_on",
                "label": "Move to a new location",
                "hint": "Advance time and seek a new angle.",
                "risk": "low",
                "tags": ["travel"],
            },
            {
                "id": "lay_low",
                "label": "Lie low and observe",
                "hint": "Lower risk but lose momentum.",
                "risk": "low",
                "tags": ["stealth"],
            },
            {
                "id": "trade",
                "label": "Trade resources for intel",
                "hint": "Spend to learn more.",
                "risk": "medium",
                "tags": ["resource"],
            },
        ]

        updates: list[dict[str, Any]] = []
        if "time" in self.variable_ids:
            updates.append(
                {
                    "op": "inc",
                    "path": "time.minute",
                    "value": 10,
                    "reason": "Action takes time",
                }
            )
        if "clues" in self.variable_ids and self.rng.random() < 0.6:
            updates.append(
                {
                    "op": "inc",
                    "path": "clues",
                    "value": 1,
                    "reason": "New clue found",
                }
            )
        if "suspicion" in self.variable_ids and self.rng.random() < 0.4:
            updates.append(
                {
                    "op": "inc",
                    "path": "suspicion",
                    "value": 2,
                    "reason": "You draw attention",
                }
            )
        if "energy" in self.variable_ids and self.rng.random() < 0.4:
            updates.append(
                {
                    "op": "dec",
                    "path": "energy",
                    "value": 5,
                    "reason": "Fatigue builds",
                }
            )
        if "truth_map" in self.variable_ids and self.rng.random() < 0.3:
            updates.append(
                {
                    "op": "push",
                    "path": "truth_map",
                    "value": "A new fragment surfaces.",
                    "reason": "Record the fact",
                }
            )
        if "location" in self.variable_ids and self.location_values and self.rng.random() < 0.2:
            updates.append(
                {
                    "op": "set",
                    "path": "location",
                    "value": self.rng.choice(self.location_values),
                    "reason": "Relocate",
                }
            )

        payload = {
            "narrative_markdown": narrative,
            "choices": choices,
            "state_updates": updates,
            "new_facts": [],
            "events": [],
            "end": {"is_game_over": False, "ending_id": "", "reason": ""},
        }

        return json.dumps(payload, ensure_ascii=False)
