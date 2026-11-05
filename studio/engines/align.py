"""Căn mốc từng từ bằng faster-whisper (local)."""
from __future__ import annotations

import re
from pathlib import Path

from ..core.project import Word

_model = None


def _get_model(size: str = "base"):
    global _model
    if _model is None:
        from faster_whisper import WhisperModel

        _model = WhisperModel(size, device="cpu", compute_type="int8")
    return _model


def align_words(audio: Path, language: str = "en") -> list[Word]:
    segments, _ = _get_model().transcribe(
        str(audio), language=language, word_timestamps=True, vad_filter=False
    )
    words: list[Word] = []
    for seg in segments:
        for w in seg.words or []:
            text = w.word.strip()
            if text:
                words.append(Word(text=text, start=float(w.start), end=float(w.end)))
    return words


_STOP = {
    "the", "a", "an", "and", "or", "but", "to", "of", "in", "on", "it", "is", "was",
    "that", "this", "for", "with", "you", "i", "my", "me", "so", "if", "not", "are",
    "be", "as", "at", "by", "do", "don't", "have", "had", "has", "just", "all",
}


def auto_emphasis(words: list[Word]) -> None:
    """Gợi ý từ khóa: từ viết hoa giữa câu hoặc từ dài, không phải stopword."""
    prev_end_punct = True
    for w in words:
        clean = re.sub(r"[^\w']", "", w.text)
        is_proper = clean[:1].isupper() and not prev_end_punct
        is_long = len(clean) >= 7 and clean.lower() not in _STOP
        w.emph = bool(is_proper or is_long)
        prev_end_punct = bool(re.search(r"[.!?]$", w.text))
