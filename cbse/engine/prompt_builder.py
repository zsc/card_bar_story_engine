from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cbse.engine.models import Choice, GameDefinition, TurnRecord, VariableDefinition


@dataclass
class PromptContext:
    game: GameDefinition
    world_markdown: str
    memory_summary: str
    state: dict[str, Any]
    recent_turns: list[TurnRecord]
    player_input: str
    last_choices: list[Choice]


class PromptBuilder:
    def __init__(
        self,
        variables: dict[str, VariableDefinition],
        compact: bool = False,
        world_max_chars: int | None = None,
    ) -> None:
        self.variables = variables
        self.compact = compact
        self.world_max_chars = world_max_chars

    def build_messages(self, ctx: PromptContext) -> list[dict[str, str]]:
        system = self._system_message()
        developer = self._developer_message(ctx)
        user = self._user_message(ctx)
        return [
            {"role": "system", "content": system},
            {"role": "developer", "content": developer},
            {"role": "user", "content": user},
        ]

    def _system_message(self) -> str:
        return (
            "You are the narrative engine. Output ONLY valid JSON matching the schema. "
            "Do not include code fences. Required fields: narrative_markdown, choices, "
            "state_updates, new_facts, events, end. choices length 3-6. "
            "state_updates length 0-6."
        )

    def _developer_message(self, ctx: PromptContext) -> str:
        world = ctx.world_markdown
        if self.compact:
            world = self._compact_world(world)
        if self.world_max_chars and len(world) > self.world_max_chars:
            world = world[: self.world_max_chars].rstrip() + "\n\n[...truncated...]"
        rules = []
        if ctx.game.prompt_rules.style_notes:
            rules.extend(ctx.game.prompt_rules.style_notes)
        if ctx.game.prompt_rules.boundaries:
            rules.extend(ctx.game.prompt_rules.boundaries)

        rule_text = "\n".join(f"- {item}" for item in rules)
        if rule_text:
            rule_text = f"\nStyle & Boundaries:\n{rule_text}"

        return (
            f"Game: {ctx.game.title} ({ctx.game.tone})\n"
            f"Content rating: {ctx.game.content_rating}\n"
            f"World:\n{world}\n"
            f"{rule_text}\n"
            "Output JSON schema (top-level):\n"
            "{\n"
            "  narrative_markdown: string,\n"
            "  choices: [{id,label,hint,risk,tags}],\n"
            "  state_updates: [{op,path,value,reason}],\n"
            "  new_facts: [string],\n"
            "  events: [{type,message}],\n"
            "  end: {is_game_over, ending_id, reason}\n"
            "}\n"
        )

    def _user_message(self, ctx: PromptContext) -> str:
        state_lines = []
        for var_id, var_def in self.variables.items():
            weight = var_def.card.prompt_weight
            if weight == "hidden":
                continue
            if self.compact and weight == "low":
                continue
            if weight not in ("high", "medium", "low"):
                continue
            value = ctx.state.get(var_id)
            state_lines.append(f"- {var_def.label} ({var_id}): {value}")
        state_text = "\n".join(state_lines)

        history_text = ""
        if ctx.memory_summary:
            history_text += f"Memory summary:\n{ctx.memory_summary}\n\n"
        if ctx.recent_turns:
            recent = []
            for turn in ctx.recent_turns:
                recent.append(f"Player: {turn.player_input}\nStory: {turn.narrative_markdown}")
            history_text += "Recent turns:\n" + "\n---\n".join(recent)

        choices_text = ""
        if ctx.last_choices:
            lines = [f"{idx+1}. {choice.label}" for idx, choice in enumerate(ctx.last_choices)]
            choices_text = "Current choices:\n" + "\n".join(lines)

        return (
            f"State:\n{state_text}\n\n"
            f"{history_text}\n\n"
            f"{choices_text}\n\n"
            f"Player input: {ctx.player_input}\n"
            "Respond with JSON only."
        )

    def _compact_world(self, text: str) -> str:
        if not text:
            return ""
        lines = text.splitlines()
        sections: list[tuple[str, list[str]]] = []
        current_title = ""
        current_lines: list[str] = []
        for line in lines:
            if line.startswith("## "):
                if current_lines:
                    sections.append((current_title, current_lines))
                current_title = line[3:].strip()
                current_lines = [line]
            else:
                current_lines.append(line)
        if current_lines:
            sections.append((current_title, current_lines))

        allow = {
            "城市与地点",
            "关键势力",
            "重要人物（可分批出场）",
            "重要人物",
            "叙事原则（必须遵守）",
            "叙事原则",
            "结局走向（方向提示）",
            "结局走向",
        }
        kept: list[str] = []
        for title, sec_lines in sections:
            if not title or title in allow:
                kept.append("\n".join(sec_lines).strip())

        # Fallback: if nothing matched, keep the first 1200 chars.
        if not kept:
            return text[:1200].rstrip() + "\n\n[...truncated...]"

        compact = "\n\n".join(part for part in kept if part)
        return compact.strip()
