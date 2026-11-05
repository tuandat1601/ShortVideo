"""Interface engine + registry. Thêm engine mới = 1 class + register()."""
from __future__ import annotations

from pathlib import Path
from typing import Protocol


class TTSEngine(Protocol):
    name: str

    def list_voices(self) -> list[str]: ...

    def synthesize(self, text: str, voice: str, dest: Path, speed: float = 1.0) -> Path: ...


_TTS: dict[str, TTSEngine] = {}


def register_tts(engine: TTSEngine) -> None:
    _TTS[engine.name] = engine


def get_tts(name: str) -> TTSEngine:
    if name not in _TTS:
        raise KeyError(f"Chưa có TTS engine '{name}'. Đã đăng ký: {list(_TTS)}")
    return _TTS[name]


def all_tts() -> dict[str, TTSEngine]:
    return dict(_TTS)
