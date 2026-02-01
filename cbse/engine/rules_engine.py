from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from cbse.engine.models import EndState, Event, StateUpdateOp, Trigger, VariableDefinition
from cbse.engine.utils import PathError, deep_get, deep_set, is_number, normalize_time


@dataclass
class RulesResult:
    state: dict[str, Any]
    applied_updates: list[StateUpdateOp]
    rejected_updates: list[StateUpdateOp]
    events: list[Event]
    end: EndState
    triggered_triggers: set[str]


class RulesEngine:
    def __init__(
        self,
        variables: dict[str, VariableDefinition],
        triggers: list[Trigger],
        win_conditions: list[str],
        lose_conditions: list[str],
    ) -> None:
        self.variables = variables
        self.triggers = sorted(triggers, key=lambda t: t.priority)
        self.win_conditions = win_conditions
        self.lose_conditions = lose_conditions

    def apply(
        self,
        state: dict[str, Any],
        updates: list[StateUpdateOp],
        triggered: set[str],
    ) -> RulesResult:
        applied: list[StateUpdateOp] = []
        rejected: list[StateUpdateOp] = []
        events: list[Event] = []

        for update in updates:
            if self._apply_update(state, update, allow_readonly=False):
                applied.append(update)
            else:
                rejected.append(update)
                events.append(Event(type="rejected_update", message=f"Rejected {update.path}"))

        self._apply_clamps(state)
        normalize_time(state)

        # Triggers
        for trigger in self.triggers:
            if trigger.once and trigger.id in triggered:
                continue
            if self._evaluate_condition(trigger.when, state):
                for effect in trigger.effects:
                    self._apply_update(state, effect, allow_readonly=True)
                events.extend(trigger.events)
                triggered.add(trigger.id)

        self._apply_clamps(state)
        normalize_time(state)

        end = self._evaluate_end(state)

        return RulesResult(
            state=state,
            applied_updates=applied,
            rejected_updates=rejected,
            events=events,
            end=end,
            triggered_triggers=triggered,
        )

    def _apply_update(self, state: dict[str, Any], update: StateUpdateOp, allow_readonly: bool) -> bool:
        root = update.path.split(".")[0]
        if root not in self.variables:
            return False
        var_def = self.variables[root]
        if var_def.rules.readonly and not allow_readonly:
            return False
        if not self._check_update_policy(var_def, update.op):
            return False

        try:
            current_value = deep_get(state, update.path)
        except PathError:
            return False

        op = update.op
        if op in ("inc", "dec"):
            if not is_number(current_value) or not is_number(update.value):
                return False
            delta = float(update.value)
            new_value = float(current_value) + (delta if op == "inc" else -delta)
            if self._is_integer(var_def, update.path, state):
                new_value = int(round(new_value))
            deep_set(state, update.path, new_value)
            return True

        if op == "set":
            if not self._check_value_type(var_def, update.path, update.value, state):
                return False
            value = update.value
            if self._is_integer(var_def, update.path, state) and is_number(value):
                value = int(round(value))
            deep_set(state, update.path, value)
            return True

        if op == "push":
            if not isinstance(current_value, list):
                return False
            current_value.append(update.value)
            return True

        if op == "remove":
            if not isinstance(current_value, list):
                return False
            if update.value in current_value:
                current_value.remove(update.value)
            return True

        if op == "toggle":
            if not isinstance(current_value, bool):
                return False
            deep_set(state, update.path, not current_value)
            return True

        return False

    def _check_update_policy(self, var_def: VariableDefinition, op: str) -> bool:
        policy = var_def.rules.update_policy
        if policy == "any":
            return True
        if policy == "inc_dec_only":
            return op in ("inc", "dec")
        if policy == "set_only":
            return op == "set"
        return True

    def _check_value_type(
        self,
        var_def: VariableDefinition,
        path: str,
        value: Any,
        state: dict[str, Any],
    ) -> bool:
        if path.split(".")[0] == var_def.id and path == var_def.id:
            return self._check_root_type(var_def, value)

        try:
            current = deep_get(state, path)
        except PathError:
            return False

        if isinstance(current, bool):
            return isinstance(value, bool)
        if isinstance(current, list):
            return isinstance(value, list)
        if isinstance(current, dict):
            return isinstance(value, dict)
        if is_number(current):
            return is_number(value)
        return isinstance(value, type(current))

    def _check_root_type(self, var_def: VariableDefinition, value: Any) -> bool:
        if var_def.type == "integer":
            return is_number(value)
        if var_def.type == "number":
            return is_number(value)
        if var_def.type == "boolean":
            return isinstance(value, bool)
        if var_def.type == "enum":
            return isinstance(value, str) and (var_def.enum_values is None or value in var_def.enum_values)
        if var_def.type == "string":
            return isinstance(value, str)
        if var_def.type == "list":
            return isinstance(value, list)
        if var_def.type == "object":
            return isinstance(value, dict)
        return True

    def _is_integer(self, var_def: VariableDefinition, path: str, state: dict[str, Any]) -> bool:
        if path == var_def.id:
            return var_def.type == "integer"
        try:
            current = deep_get(state, path)
        except PathError:
            return False
        return isinstance(current, int) and not isinstance(current, bool)

    def _apply_clamps(self, state: dict[str, Any]) -> None:
        for var_id, var_def in self.variables.items():
            if not var_def.rules.clamp:
                continue
            if var_def.type not in ("integer", "number"):
                continue
            if var_id not in state:
                continue
            value = state[var_id]
            if not is_number(value):
                continue
            if var_def.min is not None and value < var_def.min:
                value = var_def.min
            if var_def.max is not None and value > var_def.max:
                value = var_def.max
            if var_def.type == "integer":
                value = int(round(value))
            state[var_id] = value

    def _evaluate_condition(self, expr: str, state: dict[str, Any]) -> bool:
        if not expr:
            return False
        try:
            return bool(_safe_eval(expr, state))
        except Exception:
            return False

    def _evaluate_end(self, state: dict[str, Any]) -> EndState:
        lose = any(self._evaluate_condition(expr, state) for expr in self.lose_conditions)
        win = any(self._evaluate_condition(expr, state) for expr in self.win_conditions)
        if lose:
            return EndState(is_game_over=True, ending_id="lose", reason="lose")
        if win:
            return EndState(is_game_over=True, ending_id="win", reason="win")
        return EndState()


# Safe expression evaluation for trigger DSL
import ast


def _safe_eval(expr: str, state: dict[str, Any]) -> Any:
    expr = expr.replace(" true", " True").replace(" false", " False")
    tree = ast.parse(expr, mode="eval")
    return _eval_node(tree.body, state)


def _eval_node(node: ast.AST, state: dict[str, Any]) -> Any:
    if isinstance(node, ast.BoolOp):
        if isinstance(node.op, ast.And):
            return all(_eval_node(v, state) for v in node.values)
        if isinstance(node.op, ast.Or):
            return any(_eval_node(v, state) for v in node.values)
    if isinstance(node, ast.UnaryOp) and isinstance(node.op, ast.Not):
        return not _eval_node(node.operand, state)
    if isinstance(node, ast.Compare):
        left = _eval_node(node.left, state)
        for op, comparator in zip(node.ops, node.comparators):
            right = _eval_node(comparator, state)
            if isinstance(op, ast.Eq) and not (left == right):
                return False
            if isinstance(op, ast.NotEq) and not (left != right):
                return False
            if isinstance(op, ast.Lt) and not (left < right):
                return False
            if isinstance(op, ast.LtE) and not (left <= right):
                return False
            if isinstance(op, ast.Gt) and not (left > right):
                return False
            if isinstance(op, ast.GtE) and not (left >= right):
                return False
            left = right
        return True
    if isinstance(node, ast.Name):
        if node.id in ("True", "False"):
            return node.id == "True"
        if node.id == "true":
            return True
        if node.id == "false":
            return False
        if node.id in state:
            return state[node.id]
        raise ValueError(node.id)
    if isinstance(node, ast.Attribute):
        base = _eval_node(node.value, state)
        if isinstance(base, dict) and node.attr in base:
            return base[node.attr]
        raise ValueError(node.attr)
    if isinstance(node, ast.Constant):
        return node.value
    raise ValueError("Unsupported expression")
