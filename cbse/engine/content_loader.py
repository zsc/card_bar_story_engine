from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from cbse.engine.models import GameDefinition, Trigger, VariableDefinition


@dataclass
class GameContent:
    definition: GameDefinition
    world_markdown: str
    intro_markdown: str
    triggers: list[Trigger]


class ContentLoader:
    def __init__(self, base_dir: Path) -> None:
        self.base_dir = base_dir

    def load_game(self, game_id: str) -> GameContent:
        game_dir = self.base_dir / game_id
        if not game_dir.exists():
            raise FileNotFoundError(f"Game not found: {game_dir}")

        game_yaml = self._load_yaml(game_dir / "game.yaml")
        definition = GameDefinition.model_validate(game_yaml)

        world_markdown = self._read_text(game_dir / "world.md")
        intro_markdown = self._read_text(game_dir / "intro.md")
        triggers = self._load_triggers(game_dir / "triggers.yaml")

        self._ensure_initial_state(definition)

        return GameContent(
            definition=definition,
            world_markdown=world_markdown,
            intro_markdown=intro_markdown,
            triggers=triggers,
        )

    def _load_yaml(self, path: Path) -> dict[str, Any]:
        if not path.exists():
            raise FileNotFoundError(f"Missing file: {path}")
        with path.open("r", encoding="utf-8") as f:
            return yaml.safe_load(f) or {}

    def _read_text(self, path: Path) -> str:
        if not path.exists():
            return ""
        return path.read_text(encoding="utf-8")

    def _load_triggers(self, path: Path) -> list[Trigger]:
        if not path.exists():
            return []
        raw = self._load_yaml(path)
        triggers = raw.get("triggers", []) if isinstance(raw, dict) else []
        return [Trigger.model_validate(item) for item in triggers]

    def _ensure_initial_state(self, definition: GameDefinition) -> None:
        # Fill missing initial_state from variable defaults.
        state = dict(definition.initial_state)
        for var in definition.variables:
            if var.id not in state:
                state[var.id] = var.default
        definition.initial_state = state


def index_variables(variables: list[VariableDefinition]) -> dict[str, VariableDefinition]:
    return {var.id: var for var in variables}
