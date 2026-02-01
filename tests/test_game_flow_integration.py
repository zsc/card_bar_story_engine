"""
Integration test that mimics the actual game flow with Ollama.
This tests the full stack: content loading -> prompt building -> LLM -> validation.
"""

import os
from pathlib import Path

import pytest

from cbse.engine.content_loader import ContentLoader, index_variables
from cbse.engine.llm.ollama_provider import OllamaProvider
from cbse.engine.llm_service import LLMService
from cbse.engine.prompt_builder import PromptBuilder, PromptContext
from cbse.engine.schema_validator import SchemaValidator
from cbse.engine.state_store import StateStore


def _ollama_settings() -> tuple[str, str]:
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    model = "gemma3:4b"
    env_model = os.getenv("CBSE_MODEL") or os.getenv("OLLAMA_MODEL")
    if env_model:
        model = env_model
    return base_url, model


@pytest.mark.integration
def test_game_flow_first_turn() -> None:
    """Test a complete first turn as the game would do it."""
    base_url, model = _ollama_settings()
    
    # Load game content exactly like the app does
    base_dir = Path(__file__).resolve().parents[1]
    content_loader = ContentLoader(base_dir / "games")
    content = content_loader.load_game("mist_harbor")
    variables_index = index_variables(content.definition.variables)
    
    # Set up state like the app does
    store = StateStore(state=content.definition.initial_state)
    store.update_last_state()
    
    # Create prompt builder with Ollama compact settings (like app.py does)
    prompt_builder = PromptBuilder(variables_index, compact=True, world_max_chars=1600)
    
    # Create validator and LLM service
    validator = SchemaValidator()
    
    # Create Ollama provider with same settings as app.py
    # app.py uses format_mode from env or defaults to "json_schema"
    format_mode = os.getenv("CBSE_OLLAMA_FORMAT") or "json_schema"
    
    client = OllamaProvider(
        model=model,
        temperature=content.definition.llm.temperature,
        max_output_tokens=content.definition.llm.max_output_tokens,
        base_url=base_url,
        json_schema=validator.json_schema(),
        num_ctx=4096,
        format_mode=format_mode,
    )
    
    service = LLMService(client=client, validator=validator, max_retries=2)
    
    # Build prompt context like the app does on first turn
    # app.py calls _run_turn("开始", from_replay=True) on auto_start
    ctx = PromptContext(
        game=content.definition,
        world_markdown=content.world_markdown,
        memory_summary=store.memory_summary,
        state=store.state,
        recent_turns=store.history[-4:],
        player_input="开始",
        last_choices=store.last_choices,
    )
    
    messages = prompt_builder.build_messages(ctx)
    
    # Print the prompt for debugging
    print("\n" + "="*60)
    print("PROMPT MESSAGES:")
    for msg in messages:
        print(f"\n--- {msg['role']} ---")
        print(msg['content'][:500] + "..." if len(msg['content']) > 500 else msg['content'])
    print("="*60 + "\n")
    
    # Generate like the app does
    result = service.generate(messages)
    
    print(f"\nUsed fallback: {result.used_fallback}")
    print(f"Error: {result.error}")
    print(f"Raw output (first 1000 chars):\n{result.raw[:1000]}...")
    
    # Assert no fallback was used
    assert result.used_fallback is False, f"LLM output invalid: {result.error}\nRaw: {result.raw[:2000]}"
    
    # Assert we got valid choices
    assert 3 <= len(result.output.choices) <= 6, f"Expected 3-6 choices, got {len(result.output.choices)}"
    
    # Assert narrative is present
    assert result.output.narrative_markdown, "No narrative generated"
    
    print(f"\n✓ Success! Generated {len(result.output.choices)} choices")
    print(f"  Narrative preview: {result.output.narrative_markdown[:100]}...")


@pytest.mark.integration  
def test_game_flow_second_turn() -> None:
    """Test a second turn with history."""
    base_url, model = _ollama_settings()
    
    base_dir = Path(__file__).resolve().parents[1]
    content_loader = ContentLoader(base_dir / "games")
    content = content_loader.load_game("mist_harbor")
    variables_index = index_variables(content.definition.variables)
    
    store = StateStore(state=content.definition.initial_state)
    store.update_last_state()
    
    prompt_builder = PromptBuilder(variables_index, compact=True, world_max_chars=1600)
    validator = SchemaValidator()
    
    format_mode = os.getenv("CBSE_OLLAMA_FORMAT") or "json_schema"
    
    client = OllamaProvider(
        model=model,
        temperature=content.definition.llm.temperature,
        max_output_tokens=content.definition.llm.max_output_tokens,
        base_url=base_url,
        json_schema=validator.json_schema(),
        num_ctx=4096,
        format_mode=format_mode,
    )
    
    service = LLMService(client=client, validator=validator, max_retries=2)
    
    # First turn - "开始"
    ctx1 = PromptContext(
        game=content.definition,
        world_markdown=content.world_markdown,
        memory_summary=store.memory_summary,
        state=store.state,
        recent_turns=[],
        player_input="开始",
        last_choices=[],
    )
    messages1 = prompt_builder.build_messages(ctx1)
    result1 = service.generate(messages1)
    
    # Store first turn result like the app does
    from cbse.engine.models import TurnRecord
    turn1 = TurnRecord(
        turn_index=1,
        player_input="开始",
        narrative_markdown=result1.output.narrative_markdown,
        choices=result1.output.choices,
        applied_updates=[],
        rejected_updates=[],
        events=result1.output.events,
        end=result1.output.end,
    )
    store.history.append(turn1)
    store.last_choices = result1.output.choices
    
    assert result1.used_fallback is False, f"First turn failed: {result1.error}"
    
    # Second turn - pick first choice
    choice_label = result1.output.choices[0].label if result1.output.choices else "调查"
    ctx2 = PromptContext(
        game=content.definition,
        world_markdown=content.world_markdown,
        memory_summary=store.memory_summary,
        state=store.state,
        recent_turns=store.history[-4:],
        player_input=choice_label,
        last_choices=result1.output.choices,
    )
    messages2 = prompt_builder.build_messages(ctx2)
    result2 = service.generate(messages2)
    
    print(f"\nSecond turn - Used fallback: {result2.used_fallback}")
    if result2.error:
        print(f"Error: {result2.error}")
        print(f"Raw output:\n{result2.raw[:2000]}")
    
    assert result2.used_fallback is False, f"Second turn failed: {result2.error}\nRaw: {result2.raw[:2000]}"
    assert 3 <= len(result2.output.choices) <= 6
    
    print(f"\n✓ Two-turn test passed!")
