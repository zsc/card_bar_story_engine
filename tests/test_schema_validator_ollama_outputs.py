import pytest

from cbse.engine.schema_validator import SchemaError, SchemaValidator


INVALID_OUTPUT_MISSING_FIELDS = """```json
{
  "end": false,
  "choices": [
    {
      "id": "前往旧电厂，寻找...前后进出的人。",
      "label": "前往旧电厂，寻找...前后进出的人。",
      "input_value": "前往旧电厂，寻找...前后进出的人。",
      "input_type": "str"
    },
    {
      "id": "向酒...询问关于停电的信息。",
      "label": "向酒...询问关于停电的信息。",
      "input_value": "向酒吧老板询问关于停电的信息。",
      "input_type": "str"
    },
    {
      "id": "调查...",
      "label": "调查...",
      "input_value": "调查一下电厂停电...其他异常情况。",
      "input_type": "str"
    }
  ],
  "events": [
    {
      "type": "你决定开始调查停电事件。",
      "message": "你决定开始调查停电事件。",
      "input_value": "你决定开始调查停电事件。",
      "input_type": "str"
    }
  ]
}
```"""

INVALID_OUTPUT_NULL_FIELDS = """```json
{
  "narrative_markdown": null,
  "choices": null,
  "state_updates": null,
  "name": "Example",
  "value": 123
}
```"""

INVALID_OUTPUT_EMPTY = ""


def test_schema_validator_rejects_missing_fields_output():
    validator = SchemaValidator()
    with pytest.raises(SchemaError):
        validator.parse(INVALID_OUTPUT_MISSING_FIELDS)


def test_schema_validator_rejects_null_fields_output():
    validator = SchemaValidator()
    with pytest.raises(SchemaError):
        validator.parse(INVALID_OUTPUT_NULL_FIELDS)


def test_schema_validator_rejects_empty_output():
    validator = SchemaValidator()
    with pytest.raises(SchemaError):
        validator.parse(INVALID_OUTPUT_EMPTY)
