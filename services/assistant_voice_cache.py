from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any


class AssistantVoiceCache:
    def __init__(self, cache_dir: str | Path = "data/assistant_voice_cache"):
        self.cache_dir = Path(cache_dir)

    def build_key(
        self,
        *,
        provider: str,
        model: str,
        voice_id: str,
        language: str,
        text: str,
        settings: dict[str, Any] | None = None,
    ) -> str:
        payload = {
            "provider": str(provider).strip(),
            "model": str(model).strip(),
            "voice_id": str(voice_id).strip(),
            "language": str(language).strip(),
            "text": str(text),
            "settings": settings or {},
        }
        serialized = json.dumps(
            payload,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
        return hashlib.sha256(serialized).hexdigest()

    def path_for_key(self, cache_key: str) -> Path:
        return self.cache_dir / f"{cache_key}.mp3"

    def get(self, cache_key: str) -> bytes | None:
        path = self.path_for_key(cache_key)
        if not path.is_file():
            return None
        return path.read_bytes()

    def put(self, cache_key: str, audio: bytes) -> Path:
        if not audio:
            raise ValueError("Audio is required")

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        target = self.path_for_key(cache_key)

        fd, temp_name = tempfile.mkstemp(
            prefix=f"{cache_key}.",
            suffix=".tmp",
            dir=self.cache_dir,
        )
        try:
            with os.fdopen(fd, "wb") as temp_file:
                temp_file.write(audio)
                temp_file.flush()
                os.fsync(temp_file.fileno())
            os.replace(temp_name, target)
        except Exception:
            try:
                os.unlink(temp_name)
            except FileNotFoundError:
                pass
            raise

        return target
