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
        world_markdown = self._append_optional_world_sections(game_dir, world_markdown)
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

    def _append_optional_world_sections(self, game_dir: Path, base: str) -> str:
        sections: list[str] = []
        npcs_data = self._load_yaml_optional(game_dir / "npcs.yaml")
        if npcs_data:
            sections.append(self._format_npcs(npcs_data))
        items_data = self._load_yaml_optional(game_dir / "items.yaml")
        if items_data:
            sections.append(self._format_items(items_data))
        scenes = self._load_scenes(game_dir / "scenes")
        if scenes:
            sections.append(scenes)
        endings = self._read_text(game_dir / "endings.md")
        if endings.strip():
            sections.append(endings.strip())

        if not sections:
            return base
        base = base.rstrip()
        return base + "\n\n" + "\n\n".join(sections)

    def _load_yaml_optional(self, path: Path) -> dict[str, Any] | None:
        if not path.exists():
            return None
        data = self._load_yaml(path)
        return data if isinstance(data, dict) else None

    def _format_npcs(self, data: dict[str, Any]) -> str:
        npcs = data.get("npcs", [])
        if not isinstance(npcs, list) or not npcs:
            return ""
        lines = ["## 人物卡（补充）"]
        for npc in npcs:
            if not isinstance(npc, dict):
                continue
            name = npc.get("name", npc.get("id", "未知"))
            role = npc.get("role", "")
            hook = npc.get("hook", "")
            secret = npc.get("secret", "")
            summary = f"{role}" if role else "人物"
            detail_parts = []
            if hook:
                detail_parts.append(f"钩子: {hook}")
            if secret:
                detail_parts.append(f"秘密: {secret}")
            detail = "；".join(detail_parts)
            if detail:
                lines.append(f"- {name}（{summary}）：{detail}")
            else:
                lines.append(f"- {name}（{summary}）")
        return "\n".join(lines)

    def _format_items(self, data: dict[str, Any]) -> str:
        items = data.get("items", [])
        if not isinstance(items, list) or not items:
            return ""
        lines = ["## 物品卡（补充）"]
        for item in items:
            if not isinstance(item, dict):
                continue
            name = item.get("name", item.get("id", "未知"))
            desc = item.get("description", "")
            use = item.get("use", "")
            parts = []
            if desc:
                parts.append(desc)
            if use:
                parts.append(f"用途: {use}")
            detail = "；".join(parts) if parts else ""
            if detail:
                lines.append(f"- {name}：{detail}")
            else:
                lines.append(f"- {name}")
        return "\n".join(lines)

    def _load_scenes(self, scenes_dir: Path) -> str:
        if not scenes_dir.exists() or not scenes_dir.is_dir():
            return ""
        files = sorted(p for p in scenes_dir.iterdir() if p.suffix.lower() == ".md")
        if not files:
            return ""
        parts = ["## 场景包（补充）"]
        for path in files:
            text = self._read_text(path).strip()
            if text:
                parts.append(text)
        return "\n\n".join(parts)

    def _ensure_initial_state(self, definition: GameDefinition) -> None:
        # Fill missing initial_state from variable defaults.
        state = dict(definition.initial_state)
        for var in definition.variables:
            if var.id not in state:
                state[var.id] = var.default
        definition.initial_state = state


def index_variables(variables: list[VariableDefinition]) -> dict[str, VariableDefinition]:
    return {var.id: var for var in variables}
