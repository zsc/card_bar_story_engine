from cbse.engine.models import StateUpdateOp, Trigger, VariableDefinition
from cbse.engine.rules_engine import RulesEngine


def test_time_carry_and_clamp():
    variables = {
        "energy": VariableDefinition(
            id="energy",
            label="Energy",
            type="integer",
            min=0,
            max=100,
            default=50,
        ),
        "time": VariableDefinition(
            id="time",
            label="Time",
            type="object",
            default={"day": 1, "hour": 20, "minute": 55},
        ),
    }
    state = {"energy": 95, "time": {"day": 1, "hour": 20, "minute": 55}}
    updates = [
        StateUpdateOp(op="inc", path="energy", value=20, reason=""),
        StateUpdateOp(op="inc", path="time.minute", value=10, reason=""),
    ]

    engine = RulesEngine(variables, triggers=[], win_conditions=[], lose_conditions=[])
    result = engine.apply(state, updates, triggered=set())

    assert result.state["energy"] == 100
    assert result.state["time"]["hour"] == 21
    assert result.state["time"]["minute"] == 5


def test_trigger_once():
    variables = {
        "flags": VariableDefinition(
            id="flags",
            label="Flags",
            type="object",
            default={"hit": False},
        )
    }
    trigger = Trigger(
        id="hit_once",
        priority=1,
        once=True,
        when="flags.hit == false",
        effects=[StateUpdateOp(op="set", path="flags.hit", value=True, reason="")],
        events=[],
    )
    engine = RulesEngine(variables, triggers=[trigger], win_conditions=[], lose_conditions=[])
    state = {"flags": {"hit": False}}
    result = engine.apply(state, updates=[], triggered=set())
    assert result.state["flags"]["hit"] is True

    result = engine.apply(state, updates=[], triggered=result.triggered_triggers)
    assert result.state["flags"]["hit"] is True
