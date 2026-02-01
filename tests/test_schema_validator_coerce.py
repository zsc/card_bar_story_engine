from cbse.engine.schema_validator import SchemaValidator


def test_coerce_minimal_invalid_ollama_json():
    validator = SchemaValidator()
    raw = '{"choices": [{"id": "choice_1", "label": "询问绅士", "Input": "询问绅士"}], "end": false, "state_updates": [{"id": "update_1", "label": "与老板交谈", "Input": "与老板交谈"}]}'
    output = validator.coerce(raw)
    assert output.narrative_markdown
    assert 3 <= len(output.choices) <= 6
    assert output.state_updates == []
    assert output.end.is_game_over is False
