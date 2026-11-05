"""Workflow: script -> giọng đọc -> mốc từng từ."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import soundfile as sf

from ...engines import tts_kokoro  # noqa: F401  (đăng ký engine)
from ...engines.align import align_words, auto_emphasis
from ...engines.base import get_tts
from ...engines.legacy import use_legacy
from ..project import Project


def split_sentences(script: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", (script or "").strip())
    return [p.strip() for p in parts if p.strip()]


def build_voiceover(proj: Project, gap_s: float = 0.18) -> Project:
    """Đọc từng câu, nối lại, áp style (ffmpeg), căn từng từ. Ghi vào proj."""
    sentences = split_sentences(proj.script)
    if not sentences:
        raise ValueError("Script trống.")
    engine = get_tts(proj.voice.engine)
    proj.build_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[np.ndarray] = []
    sr = None
    for i, sent in enumerate(sentences):
        wav = proj.build_dir / f"s{i:03d}.wav"
        engine.synthesize(sent, proj.voice.voice, wav, speed=proj.voice.speed)
        data, rate = sf.read(str(wav), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        sr = sr or rate
        chunks.append(data)
        chunks.append(np.zeros(int(gap_s * rate), dtype=np.float32))
    raw = proj.build_dir / "voice_raw.wav"
    sf.write(str(raw), np.concatenate(chunks[:-1]), sr)

    use_legacy()
    from dub import apply_speed_volume, style_defaults  # type: ignore

    _spd, vol, _ = style_defaults(proj.voice.style)
    final = proj.media_dir / "voice.wav"
    proj.media_dir.mkdir(parents=True, exist_ok=True)
    # tốc độ đã áp ở TTS; ở đây chỉ lấy EQ/âm lượng của style (speed=1.0)
    apply_speed_volume(raw, final, 1.0, vol, style=proj.voice.style)

    proj.voice_file = "media/voice.wav"
    proj.words = align_words(final)
    auto_emphasis(proj.words)
    proj.save()
    return proj


def auto_broll(proj: Project) -> Project:
    """Tự chia các file media hiện có theo từng câu (hoặc chia đều thời lượng)."""
    from ..project import Clip

    exts = {".png", ".jpg", ".jpeg", ".webp", ".mp4", ".mov", ".webm", ".mkv", ".m4v"}
    files = sorted(
        f"media/{p.name}"
        for p in (proj.media_dir.iterdir() if proj.media_dir.exists() else [])
        if p.is_file() and p.suffix.lower() in exts and p.name != "voice.wav"
    )
    if not files:
        raise ValueError("Chưa có ảnh/video nào trong Media.")

    # Tìm mốc kết thúc mỗi câu từ words
    spans: list[tuple[float, float]] = []
    if proj.words:
        s0 = 0.0
        for w in proj.words:
            if w.text.rstrip()[-1:] in ".!?":
                spans.append((s0, w.end))
                s0 = w.end
        if s0 < proj.words[-1].end:
            spans.append((s0, proj.words[-1].end))
    if not spans:
        dur = max(proj.duration, len(files) * 2.5)
        step = dur / len(files)
        spans = [(i * step, (i + 1) * step) for i in range(len(files))]

    proj.clips = [
        Clip(
            src=files[i % len(files)],
            start=round(st, 2),
            dur=round(max(en - st, 0.4), 2),
            fit="cover",
        )
        for i, (st, en) in enumerate(spans)
    ]
    proj.save()
    return proj

