from cbse.engine.models import StateUpdateOp, Trigger, VariableDefinition
from cbse.engine.rules_engine import RulesEngine


def _base_variables():
    return {
        "hp": VariableDefinition(
            id="hp",
            label="HP",
            type="integer",
            min=0,
            max=100,
            default=50,
        ),
        "flag": VariableDefinition(
            id="flag",
            label="Flag",
            type="boolean",
            default=False,
        ),
        "items": VariableDefinition(
            id="items",
            label="Items",
            type="list",
            default=[],
        ),
        "mode": VariableDefinition(
            id="mode",
            label="Mode",
            type="enum",
            enum_values=["a", "b"],
            default="a",
        ),
        "readonly": VariableDefinition(
            id="readonly",
            label="RO",
            type="integer",
            default=1,
            rules={"readonly": True},
        ),
        "inc_only": VariableDefinition(
            id="inc_only",
            label="IncOnly",
            type="integer",
            default=0,
            rules={"update_policy": "inc_dec_only"},
        ),
        "set_only": VariableDefinition(
            id="set_only",
            label="SetOnly",
            type="enum",
            enum_values=["x", "y"],
            default="x",
            rules={"update_policy": "set_only"},
        ),
    }


def test_inc_dec_clamp():
    variables = _base_variables()
    state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }
    updates = [
        StateUpdateOp(op="inc", path="hp", value=100, reason=""),
        StateUpdateOp(op="dec", path="hp", value=30, reason=""),
    ]
    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])
    result = engine.apply(state, updates, triggered=set())
    assert result.state["hp"] == 100
    assert len(result.applied_updates) == 2
    assert not result.rejected_updates


def test_set_enum_and_reject_invalid_enum():
    variables = _base_variables()
    state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }
    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])

    ok = engine.apply(
        state,
        [StateUpdateOp(op="set", path="mode", value="b", reason="")],
        triggered=set(),
    )
    assert ok.state["mode"] == "b"
    assert len(ok.applied_updates) == 1

    bad = engine.apply(
        state,
        [StateUpdateOp(op="set", path="mode", value="c", reason="")],
        triggered=set(),
    )
    assert len(bad.applied_updates) == 0
    assert len(bad.rejected_updates) == 1


def test_push_remove_list():
    variables = _base_variables()
    state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }
    updates = [
        StateUpdateOp(op="push", path="items", value="key", reason=""),
        StateUpdateOp(op="remove", path="items", value="key", reason=""),
    ]
    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])
    result = engine.apply(state, updates, triggered=set())
    assert result.state["items"] == []
    assert len(result.applied_updates) == 2


def test_toggle_boolean():
    variables = _base_variables()
    state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }
    updates = [StateUpdateOp(op="toggle", path="flag", value=None, reason="")]
    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])
    result = engine.apply(state, updates, triggered=set())
    assert result.state["flag"] is True


def test_update_policy_enforced():
    variables = _base_variables()
    state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }
    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])

    bad_set = engine.apply(
        state,
        [StateUpdateOp(op="set", path="inc_only", value=5, reason="")],
        triggered=set(),
    )
    assert len(bad_set.applied_updates) == 0

    bad_inc = engine.apply(
        state,
        [StateUpdateOp(op="inc", path="set_only", value=1, reason="")],
        triggered=set(),
    )
    assert len(bad_inc.applied_updates) == 0


def test_readonly_rejects_but_trigger_allows():
    variables = _base_variables()
    base_state = {
        "hp": 50,
        "flag": False,
        "items": [],
        "mode": "a",
        "readonly": 1,
        "inc_only": 0,
        "set_only": "x",
    }

    engine_no_trigger = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])
    bad = engine_no_trigger.apply(
        dict(base_state),
        [StateUpdateOp(op="set", path="readonly", value=2, reason="")],
        triggered=set(),
    )
    assert len(bad.applied_updates) == 0
    assert bad.state["readonly"] == 1

    trigger = Trigger(
        id="set_readonly",
        priority=1,
        once=True,
        when="true",
        effects=[StateUpdateOp(op="set", path="readonly", value=42, reason="")],
        events=[],
    )
    engine_trigger = RulesEngine(variables, triggers=[trigger], win_conditions=[], lose_conditions=[])
    ok = engine_trigger.apply(dict(base_state), [], triggered=set())
    assert ok.state["readonly"] == 42
