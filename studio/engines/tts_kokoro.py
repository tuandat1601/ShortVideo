from __future__ import annotations

from pathlib import Path

from .base import register_tts
from .legacy import use_legacy


class KokoroTTS:
    name = "kokoro"

    def list_voices(self) -> list[str]:
        use_legacy()
        import tts_en

        return tts_en.list_english_voice_choices() if tts_en.is_available() else []

    def synthesize(self, text: str, voice: str, dest: Path, speed: float = 1.0) -> Path:
        use_legacy()
        import tts_en

        tts_en.synthesize_english(text, voice, dest, speed=speed)
        return dest


register_tts(KokoroTTS())
