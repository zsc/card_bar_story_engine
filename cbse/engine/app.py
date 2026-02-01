from __future__ import annotations

import json
import os
import argparse
from pathlib import Path
from typing import Any

from textual.app import App, ComposeResult
from textual.containers import Horizontal, Vertical
from textual.widgets import Footer, Input, Markdown, Static

from cbse.engine.content_loader import ContentLoader, GameContent, index_variables
from cbse.engine.llm import GeminiProvider, MockProvider, OpenAIProvider
from cbse.engine.llm_service import LLMResult, LLMService
from cbse.engine.models import Choice, EndState, Event, TurnRecord
from cbse.engine.prompt_builder import PromptBuilder, PromptContext
from cbse.engine.replay import load_replay_inputs
from cbse.engine.rules_engine import RulesEngine
from cbse.engine.save_system import SaveSystem
from cbse.engine.schema_validator import SchemaValidator
from cbse.engine.state_store import StateStore
from cbse.engine.utils import deep_get


def _format_value(value: Any) -> str:
    if isinstance(value, dict) and {"hour", "minute"}.issubset(value.keys()):
        day = value.get("day", 1)
        hour = value.get("hour", 0)
        minute = value.get("minute", 0)
        return f"D{day} {int(hour):02d}:{int(minute):02d}"
    if isinstance(value, dict):
        return json.dumps(value, ensure_ascii=False)
    if isinstance(value, list):
        return ", ".join(str(item) for item in value) if value else "(empty)"
    return str(value)


class StatusBarWidget(Static):
    def render_status(self, content: GameContent, store: StateStore) -> None:
        parts: list[str] = []
        for item in content.definition.status_bar.items:
            try:
                value = deep_get(store.state, item.var_id)
            except Exception:
                value = "?"
            value = _format_value(value)
            label = item.label
            text = f"{label}: {value}"
            delta = store.get_delta(item.var_id)
            if item.show_delta and delta and delta.numeric_delta:
                text += f" ({delta.numeric_delta:+.0f})"
            if item.critical_threshold is not None and isinstance(value, (int, float)):
                if value <= item.critical_threshold:
                    text += " !"
            parts.append(text)
        self.update(" | ".join(parts))


class VariablePanel(Static):
    def render_panel(self, content: GameContent, store: StateStore) -> None:
        cards = [
            var
            for var in content.definition.variables
            if var.card.visible
        ]
        cards.sort(key=lambda v: v.card.order)

        lines: list[str] = []
        for var in cards:
            value = _format_value(store.state.get(var.id))
            delta = store.get_delta(var.id)
            header = f"[{var.label}]"
            if delta and delta.changed and delta.summary:
                header += f"  Δ {delta.summary}"
            lines.append(header)
            lines.append(f"{value}")
            if var.card.description:
                lines.append(var.card.description)
            lines.append("")

        self.update("\n".join(lines).strip())


class ChoicesWidget(Static):
    def render_choices(self, choices: list[Choice]) -> None:
        if not choices:
            self.update("(no choices yet)")
            return
        lines = []
        for idx, choice in enumerate(choices, start=1):
            hint = f" - {choice.hint}" if choice.hint else ""
            lines.append(f"{idx}. {choice.label}{hint}")
        self.update("\n".join(lines))


class EventsWidget(Static):
    def render_events(self, events: list[Event]) -> None:
        if not events:
            self.update("")
            return
        lines = [f"[{event.type}] {event.message}" for event in events]
        self.update("\n".join(lines))


class CardBarApp(App):
    CSS = """
    Screen { layout: vertical; }
    #header { height: 2; content-align: left middle; }
    #status { height: 2; content-align: left middle; }
    #main { height: 1fr; }
    #side { width: 34; border: round $accent; padding: 1; }
    #story { border: round $accent; padding: 1; height: 1fr; }
    #choices { border: round $accent; padding: 1; height: 12; }
    #events { border: round $accent; padding: 1; height: 6; }
    #input { height: 3; }
    """

    def __init__(self, replay_file: str | None = None, game_id: str = "mist_harbor") -> None:
        super().__init__()
        self.base_dir = Path(__file__).resolve().parents[2]
        self.content_loader = ContentLoader(self.base_dir / "games")
        self.content: GameContent | None = None
        self.variables_index: dict[str, Any] = {}
        self.store: StateStore | None = None
        self.prompt_builder: PromptBuilder | None = None
        self.rules_engine: RulesEngine | None = None
        self.validator = SchemaValidator()
        self.llm_service: LLMService | None = None
        self.save_system = SaveSystem(self.base_dir / "saves")
        self.log_dir = self.base_dir / "logs"
        self.log_dir.mkdir(parents=True, exist_ok=True)
        self.last_prompt: list[dict[str, str]] | None = None
        self.last_failed: bool = False
        self.latest_raw: str = ""
        self.latest_events: list[Event] = []
        self.replay_file = replay_file
        self.replay_inputs: list[str] = []
        self.replay_active: bool = False
        self.game_id = game_id

    def compose(self) -> ComposeResult:
        yield Static("", id="header")
        yield StatusBarWidget(id="status")
        with Horizontal(id="main"):
            yield VariablePanel(id="side")
            with Vertical():
                yield Markdown("", id="story")
                yield ChoicesWidget(id="choices")
                yield EventsWidget(id="events")
        yield Input(placeholder="Enter a number or action...", id="input")
        yield Footer()

    def on_mount(self) -> None:
        self.load_game(self.game_id)
        self.refresh_ui()
        if self.replay_file:
            self._start_replay(self.replay_file)

    def load_game(self, game_id: str) -> None:
        content = self.content_loader.load_game(game_id)
        self.content = content
        self.variables_index = index_variables(content.definition.variables)
        self.store = StateStore(state=content.definition.initial_state)
        self.store.update_last_state()
        self.prompt_builder = PromptBuilder(self.variables_index)
        self.rules_engine = RulesEngine(
            self.variables_index,
            content.triggers,
            content.definition.win_conditions,
            content.definition.lose_conditions,
        )
        self.llm_service = self._create_llm_service()
        header = self.query_one("#header", Static)
        header.update(f"{content.definition.title} - {content.definition.tone}")

        # Intro narrative
        story = self.query_one("#story", Markdown)
        intro = content.intro_markdown.strip() if content.intro_markdown else ""
        if intro:
            story.update(intro)

        choices = self.query_one("#choices", ChoicesWidget)
        choices.render_choices([])

    def _create_llm_service(self) -> LLMService:
        assert self.content is not None
        provider = os.getenv("CBSE_LLM_PROVIDER", "mock").lower()
        model = os.getenv("CBSE_MODEL", self.content.definition.llm.recommended_model or "gpt-4.1-mini")
        temp = self.content.definition.llm.temperature
        max_tokens = self.content.definition.llm.max_output_tokens

        if provider == "openai":
            client = OpenAIProvider(model=model, temperature=temp, max_output_tokens=max_tokens)
        elif provider == "gemini":
            client = GeminiProvider(model=model, temperature=temp, max_output_tokens=max_tokens)
        else:
            locations = []
            for var in self.content.definition.variables:
                if var.id == "location" and var.enum_values:
                    locations = var.enum_values
            client = MockProvider(set(self.variables_index.keys()), locations)

        return LLMService(client=client, validator=self.validator)

    def refresh_ui(self) -> None:
        if not self.content or not self.store:
            return
        status = self.query_one("#status", StatusBarWidget)
        status.render_status(self.content, self.store)

        side = self.query_one("#side", VariablePanel)
        side.render_panel(self.content, self.store)

    def on_input_submitted(self, event: Input.Submitted) -> None:
        text = event.value.strip()
        event.input.value = ""
        if not text:
            return
        if text.startswith("/"):
            self._handle_command(text)
            return
        if self.last_failed:
            self._handle_failure_choice(text)
            return
        self._run_turn(text, from_replay=False)

    def _handle_failure_choice(self, text: str) -> None:
        choice = self._resolve_choice(text)
        if not choice and text.lower() in {"retry", "rollback", "exit"}:
            choice = Choice(id=text.lower(), label=text, hint="", risk="low", tags=["system"])
        if not choice:
            return
        if choice.id == "retry" and self.last_prompt:
            self._run_turn("retry", use_last_prompt=True)
            return
        if choice.id == "rollback":
            self.last_failed = False
            return
        if choice.id == "exit":
            self.exit()

    def _handle_command(self, text: str) -> None:
        parts = text.split()
        command = parts[0].lower()
        if command == "/quit":
            self.exit()
            return
        if command == "/help":
            self._show_system_message(
                "Commands: /save <name>, /load <name>, /replay <path>, /replay stop, /quit, /help"
            )
            return
        if command == "/save" and len(parts) >= 2:
            name = parts[1]
            self._save_game(name)
            return
        if command == "/load" and len(parts) >= 2:
            name = parts[1]
            self._load_game(name)
            return
        if command == "/replay" and len(parts) == 2 and parts[1].lower() == "stop":
            self._stop_replay()
            return
        if command == "/replay" and len(parts) >= 2:
            path = " ".join(parts[1:])
            self._start_replay(path)
            return
        self._show_system_message("Unknown command")

    def _save_game(self, name: str) -> None:
        if not self.content or not self.store:
            return
        self.save_system.save(name, self.store, self.content.definition.game_id, self.content.definition.version)
        self._show_system_message(f"Saved: {name}")

    def _load_game(self, name: str) -> None:
        if not self.content:
            return
        save = self.save_system.load(name)
        if save.game_id != self.content.definition.game_id:
            self._show_system_message("Save game_id mismatch")
            return
        self.store = StateStore(state=save.state)
        self.store.history = save.history
        self.store.memory_summary = save.memory_summary
        self.store.triggered_triggers = set(save.triggered_triggers)
        self.store.update_last_state()
        self.refresh_ui()
        self._show_system_message(f"Loaded: {name}")

    def _show_system_message(self, message: str) -> None:
        story = self.query_one("#story", Markdown)
        story.update(f"**System**: {message}")

    def _resolve_choice(self, text: str) -> Choice | None:
        if not self.store:
            return None
        if text.isdigit():
            idx = int(text) - 1
            if 0 <= idx < len(self.store.last_choices):
                return self.store.last_choices[idx]
        return None

    def _run_turn(self, text: str, use_last_prompt: bool = False, from_replay: bool = False) -> None:
        assert self.content is not None
        assert self.store is not None
        assert self.prompt_builder is not None
        assert self.rules_engine is not None
        assert self.llm_service is not None

        if self.replay_active and not from_replay:
            self._stop_replay()

        self.store.update_last_state()
        choice = self._resolve_choice(text)
        player_input = choice.label if choice else text

        if use_last_prompt and self.last_prompt:
            messages = self.last_prompt
        else:
            ctx = PromptContext(
                game=self.content.definition,
                world_markdown=self.content.world_markdown,
                memory_summary=self.store.memory_summary,
                state=self.store.state,
                recent_turns=self.store.history[-4:],
                player_input=player_input,
                last_choices=self.store.last_choices,
            )
            messages = self.prompt_builder.build_messages(ctx)
            self.last_prompt = messages

        result = self.llm_service.generate(messages)
        self.latest_raw = result.raw
        output = result.output

        rules = self.rules_engine.apply(self.store.state, output.state_updates, self.store.triggered_triggers)
        self.store.state = rules.state
        self.store.triggered_triggers = rules.triggered_triggers
        self.store.compute_deltas()
        self.last_failed = result.used_fallback

        events = output.events + rules.events
        end = rules.end if rules.end.is_game_over else output.end

        turn = TurnRecord(
            turn_index=len(self.store.history) + 1,
            player_input=player_input,
            narrative_markdown=output.narrative_markdown,
            choices=output.choices,
            applied_updates=rules.applied_updates,
            rejected_updates=rules.rejected_updates,
            events=events,
            end=end,
        )
        self.store.history.append(turn)
        self.store.last_choices = output.choices
        self._update_memory_summary()

        self._update_turn_view(output.narrative_markdown, output.choices, events, end)
        self.refresh_ui()
        self._log_turn(messages, result, turn)

        if end.is_game_over:
            self._show_system_message(f"Game Over: {end.reason}")
            self._stop_replay()
            return

        if self.last_failed:
            self._stop_replay()
            return

        if self.replay_active:
            self.call_later(self._advance_replay)

    def _update_turn_view(
        self,
        narrative: str,
        choices: list[Choice],
        events: list[Event],
        end: EndState,
    ) -> None:
        story = self.query_one("#story", Markdown)
        story.update(narrative)
        choices_widget = self.query_one("#choices", ChoicesWidget)
        choices_widget.render_choices(choices)
        events_widget = self.query_one("#events", EventsWidget)
        events_widget.render_events(events)

    def _update_memory_summary(self) -> None:
        if not self.store:
            return
        if len(self.store.history) % 5 != 0:
            return
        recent = self.store.history[-5:]
        snippets = []
        for turn in recent:
            snippet = turn.narrative_markdown.strip().replace("\n", " ")
            snippets.append(snippet[:120])
        self.store.memory_summary = " | ".join(snippets)[:600]

    def _log_turn(self, messages: list[dict[str, str]], result: LLMResult, turn: TurnRecord) -> None:
        payload = {
            "turn_index": turn.turn_index,
            "player_input": turn.player_input,
            "prompt": messages,
            "raw_output": result.raw,
            "used_fallback": result.used_fallback,
            "applied_updates": [u.model_dump() for u in turn.applied_updates],
            "rejected_updates": [u.model_dump() for u in turn.rejected_updates],
            "events": [e.model_dump() for e in turn.events],
            "end": turn.end.model_dump(),
        }
        path = self.log_dir / "turns.jsonl"
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(payload, ensure_ascii=False) + "\n")

    def _start_replay(self, path_text: str) -> None:
        path = Path(path_text)
        if not path.exists():
            alt = self.base_dir / path_text
            if alt.exists():
                path = alt
        try:
            inputs = load_replay_inputs(path)
        except Exception as exc:
            self._show_system_message(f"Replay load failed: {exc}")
            return
        if not inputs:
            self._show_system_message("Replay file is empty")
            return
        self.replay_inputs = inputs
        self.replay_active = True
        self._show_system_message(f"Replay started ({len(inputs)} steps)")
        self.call_later(self._advance_replay)

    def _advance_replay(self) -> None:
        if not self.replay_active:
            return
        if not self.replay_inputs:
            self._show_system_message("Replay finished")
            self._stop_replay()
            return
        next_input = self.replay_inputs.pop(0)
        self._run_turn(next_input, from_replay=True)

    def _stop_replay(self) -> None:
        self.replay_active = False
        self.replay_inputs = []


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--game", dest="game", default="mist_harbor", help="Game id under games/")
    parser.add_argument("--replay", dest="replay", help="Replay input bag file")
    args, _ = parser.parse_known_args()
    CardBarApp(replay_file=args.replay, game_id=args.game).run()
