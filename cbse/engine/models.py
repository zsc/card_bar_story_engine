from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator


class VariableCard(BaseModel):
    model_config = ConfigDict(extra="forbid")

    visible: bool = True
    order: int = 0
    format: Literal["bar", "plain", "list", "chips", "keyvalue"] = "plain"
    description: str = ""
    prompt_weight: Literal["high", "medium", "low", "hidden"] = "medium"


class VariableRules(BaseModel):
    model_config = ConfigDict(extra="forbid")

    clamp: bool = True
    readonly: bool = False
    update_policy: Literal["any", "inc_dec_only", "set_only"] = "any"


class VariableDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    type: Literal["number", "integer", "boolean", "enum", "string", "list", "object"]
    min: float | None = None
    max: float | None = None
    enum_values: list[str] | None = None
    default: Any = None
    card: VariableCard = Field(default_factory=VariableCard)
    rules: VariableRules = Field(default_factory=VariableRules)
    tags: list[str] = Field(default_factory=list)


class StatusBarItem(BaseModel):
    model_config = ConfigDict(extra="forbid")

    var_id: str
    style: Literal["meter", "text"] = "text"
    label: str
    show_delta: bool = False
    critical_threshold: float | None = None


class StatusBarDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    items: list[StatusBarItem]


class LLMConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    recommended_model: str | None = None
    temperature: float = 0.7
    max_output_tokens: int = 900


class PromptRules(BaseModel):
    model_config = ConfigDict(extra="allow")

    style_notes: list[str] = Field(default_factory=list)
    boundaries: list[str] = Field(default_factory=list)


class GameDefinition(BaseModel):
    model_config = ConfigDict(extra="forbid")

    game_id: str
    title: str
    version: str
    language: str = "zh-CN"
    tone: str = ""
    content_rating: str = "PG-13"

    status_bar: StatusBarDefinition
    variables: list[VariableDefinition]
    initial_state: dict[str, Any]
    win_conditions: list[str] = Field(default_factory=list)
    lose_conditions: list[str] = Field(default_factory=list)
    llm: LLMConfig = Field(default_factory=LLMConfig)
    prompt_rules: PromptRules = Field(default_factory=PromptRules)


class Choice(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    label: str
    hint: str = ""
    risk: Literal["low", "medium", "high"] = "low"
    tags: list[str] = Field(default_factory=list)


class StateUpdateOp(BaseModel):
    model_config = ConfigDict(extra="forbid")

    op: Literal["set", "inc", "dec", "push", "remove", "toggle"]
    path: str
    value: Any = None
    reason: str = ""


class Event(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: str
    message: str


class EndState(BaseModel):
    model_config = ConfigDict(extra="forbid")

    is_game_over: bool = False
    ending_id: str = ""
    reason: str = ""


class LLMOutput(BaseModel):
    model_config = ConfigDict(extra="forbid")

    narrative_markdown: str
    choices: list[Choice]
    state_updates: list[StateUpdateOp]
    new_facts: list[str] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)
    end: EndState = Field(default_factory=EndState)

    @model_validator(mode="after")
    def validate_counts(self) -> "LLMOutput":
        if not (3 <= len(self.choices) <= 6):
            raise ValueError("choices must be 3-6")
        if len(self.state_updates) > 6:
            raise ValueError("state_updates must be 0-6")
        return self


class Trigger(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id: str
    priority: int = 100
    once: bool = False
    when: str
    effects: list[StateUpdateOp] = Field(default_factory=list)
    events: list[Event] = Field(default_factory=list)


class TurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")

    turn_index: int
    player_input: str
    narrative_markdown: str
    choices: list[Choice]
    applied_updates: list[StateUpdateOp]
    rejected_updates: list[StateUpdateOp]
    events: list[Event]
    end: EndState


class SaveGame(BaseModel):
    model_config = ConfigDict(extra="forbid")

    save_version: str
    game_id: str
    game_content_version: str
    timestamp: str
    turn_index: int
    state: dict[str, Any]
    history: list[TurnRecord]
    memory_summary: str = ""
    triggered_triggers: list[str] = Field(default_factory=list)
