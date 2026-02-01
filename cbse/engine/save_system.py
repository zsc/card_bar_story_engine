from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

from cbse.engine.models import SaveGame, TurnRecord
from cbse.engine.state_store import StateStore


SAVE_VERSION = "1.0"


class SaveSystem:
    def __init__(self, save_dir: Path) -> None:
        self.save_dir = save_dir
        self.save_dir.mkdir(parents=True, exist_ok=True)

    def save(self, name: str, store: StateStore, game_id: str, game_version: str) -> Path:
        payload = SaveGame(
            save_version=SAVE_VERSION,
            game_id=game_id,
            game_content_version=game_version,
            timestamp=datetime.utcnow().isoformat(),
            turn_index=len(store.history),
            state=store.state,
            history=store.history,
            memory_summary=store.memory_summary,
            triggered_triggers=sorted(store.triggered_triggers),
        )
        path = self.save_dir / f"{name}.json"
        path.write_text(payload.model_dump_json(indent=2), encoding="utf-8")
        return path

    def load(self, name: str) -> SaveGame:
        path = self.save_dir / f"{name}.json"
        if not path.exists():
            raise FileNotFoundError(f"Save not found: {path}")
        data = json.loads(path.read_text(encoding="utf-8"))
        return SaveGame.model_validate(data)
