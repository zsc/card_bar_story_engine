# CardBar Story Engine (CBSE)

Python + Textual AI narrative game engine (MVP).

## Quick Start

```bash
python -m cbse
```

Defaults to the Mock LLM (offline friendly).

## LLM Provider

Select via environment variables:

- `CBSE_LLM_PROVIDER=mock|openai|gemini`
- `CBSE_MODEL` 覆盖模型名（可选）
- `OPENAI_API_KEY` 或 `GEMINI_API_KEY`

> openai/gemini providers are minimal and may change with upstream APIs.

## Save/Load

In the input box:

- `/save <name>`
- `/load <name>`
- `/replay <path>`
- `/replay stop`
- `/quit`
- `/help`

Saves are written to `saves/`.

## Game Content

Default game: `games/mist_harbor/`. Extend via `game.yaml` + `world.md` + `triggers.yaml`.

## Replay

Replay a pre-written engine-user-input bag:

```bash
python -m cbse --replay replays/mist_harbor_demo.jsonl
```

Supported formats:

- JSON array: `["look around", "ask about the outage"]`
- JSON object: `{"inputs": ["look around", "ask about the outage"]}`
- JSONL: one `{"input": "..."}`
- Plain text: one input per line, `#` for comments
