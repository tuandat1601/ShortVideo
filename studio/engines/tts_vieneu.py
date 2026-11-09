"""TTS Engine cho tiếng Việt & giọng clone (dùng VieNeu qua long-tieng/app.py)."""
from __future__ import annotations

from pathlib import Path

from .base import register_tts
from .legacy import use_legacy


class VieNeuTTS:
    name = "vieneu"

    def list_voices(self) -> list[str]:
        use_legacy()
        import app

        return app.list_file_voices()

    def synthesize(self, text: str, voice: str, dest: Path, speed: float = 1.0) -> Path:
        use_legacy()
        import app

        app.synthesize_to_wav(voice, text, dest)
        return dest


register_tts(VieNeuTTS())
