import os

import pytest

from cbse.engine.llm.ollama_provider import OllamaProvider
from cbse.engine.llm_service import LLMService
from cbse.engine.schema_validator import SchemaValidator


def _ollama_settings() -> tuple[str, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = "gemma3:1b"
    env_model = os.getenv("CBSE_MODEL") or os.getenv("OLLAMA_MODEL")
    if env_model:
        model = env_model
    return base_url, model


@pytest.mark.integration
def test_ollama_schema_compliance() -> None:
    base_url, model = _ollama_settings()
    validator = SchemaValidator()
    client = OllamaProvider(
        model=model,
        temperature=0.0,
        max_output_tokens=600,
        base_url=base_url,
        json_schema=validator.json_schema(),
        timeout=30.0,
        format_mode="json_schema",
        num_ctx=4096,
    )
    service = LLMService(client=client, validator=validator, max_retries=2)

    # Provide a complete example of the expected JSON format
    example_json = """{
  "narrative_markdown": "夜幕降临，街道上空无一人。",
  "choices": [
    {"id": "1", "label": "回家", "hint": "安全的选择", "risk": "low", "tags": ["safe"]},
    {"id": "2", "label": "继续调查", "hint": "可能有危险", "risk": "medium", "tags": ["risk"]},
    {"id": "3", "label": "寻求帮助", "hint": "找朋友帮忙", "risk": "low", "tags": ["social"]}
  ],
  "state_updates": [],
  "new_facts": [],
  "events": [{"type": "info", "message": "测试事件"}],
  "end": {"is_game_over": false, "ending_id": "", "reason": ""}
}"""

    messages = [
        {
            "role": "system",
            "content": (
                "You are a game engine. Return ONLY valid JSON. "
                "No markdown, no explanations, no thinking tags, no comments. "
                "Follow the exact structure shown in the example."
            ),
        },
        {
            "role": "user",
            "content": (
                f"Example format:\n{example_json}\n\n"
                "Now generate a response in the same format. "
                "Use Chinese for narrative_markdown and label fields. "
                "Provide exactly 3 choices with risk levels (low/medium/high). "
                "Keep state_updates, new_facts, events as empty arrays []."
            ),
        },
    ]

    result = service.generate(messages)
    assert result.used_fallback is False, result.error
    assert 3 <= len(result.output.choices) <= 6
