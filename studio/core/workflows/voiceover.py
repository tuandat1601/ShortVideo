"""Workflow: script -> giọng đọc -> mốc từng từ."""
from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import soundfile as sf

from ...engines import tts_kokoro, tts_vieneu  # noqa: F401  (đăng ký engine)
from ...engines.align import align_words, auto_emphasis
from ...engines.base import get_tts
from ...engines.legacy import use_legacy
from ..project import Project, VoiceSegment, Word


def split_sentences(script: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", (script or "").strip())
    return [p.strip() for p in parts if p.strip()]


def build_single_segment(proj: Project, seg: VoiceSegment, gap_s: float = 0.18) -> VoiceSegment:
    """Đọc riêng 1 đoạn thoại (segment), căn mốc từng từ của đoạn đó."""
    cleaned = (seg.text or "").strip()
    if not cleaned:
        seg.words = []
        seg.dur = 0.0
        return seg

    sentences = split_sentences(cleaned)
    engine_name = "kokoro" if seg.voice.startswith("【EN") else "vieneu"
    seg.engine = engine_name
    engine = get_tts(engine_name)
    proj.build_dir.mkdir(parents=True, exist_ok=True)
    proj.media_dir.mkdir(parents=True, exist_ok=True)

    chunks: list[np.ndarray] = []
    sr = None
    for i, sent in enumerate(sentences):
        wav = proj.build_dir / f"s_{seg.id}_{i:03d}.wav"
        engine.synthesize(sent, seg.voice, wav, speed=seg.speed)
        data, rate = sf.read(str(wav), dtype="float32")
        if data.ndim > 1:
            data = data.mean(axis=1)
        sr = sr or rate
        chunks.append(data)
        chunks.append(np.zeros(int(gap_s * rate), dtype=np.float32))

    raw = proj.build_dir / f"raw_{seg.id}.wav"
    sf.write(str(raw), np.concatenate(chunks[:-1]), sr)

    use_legacy()
    from dub import apply_speed_volume, style_defaults  # type: ignore

    _spd, vol, _ = style_defaults(seg.style)
    final = proj.media_dir / f"v_{seg.id}.wav"
    apply_speed_volume(raw, final, 1.0, vol, style=seg.style)

    final_data, final_sr = sf.read(str(final), dtype="float32")
    seg.dur = round(float(len(final_data)) / float(final_sr), 3)
    seg.file = f"media/v_{seg.id}.wav"

    seg_words = align_words(final)
    auto_emphasis(seg_words)
    for w in seg_words:
        w.start = round(w.start + seg.start, 3)
        w.end = round(w.end + seg.start, 3)
    seg.words = seg_words
    return seg


def assemble_master_voice(proj: Project) -> Project:
    """Ghép tất cả các đoạn thoại vào media/voice.wav theo đúng vị trí start trên timeline."""
    if not proj.voice_segments:
        return proj

    sr = 48000
    max_end = max((s.start + max(s.dur, 0.2) for s in proj.voice_segments), default=1.0)
    total_len = max(int(round((max_end + 0.3) * sr)), sr)
    mix = np.zeros(total_len, dtype=np.float32)

    all_words: list[Word] = []
    for s in proj.voice_segments:
        if s.file:
            fpath = proj.dir / s.file
            if fpath.exists():
                audio, in_sr = sf.read(str(fpath), dtype="float32")
                if audio.ndim > 1:
                    audio = audio.mean(axis=1)
                if in_sr != sr:
                    try:
                        import soxr
                        audio = soxr.resample(audio, int(in_sr), sr)
                    except Exception:
                        pass
                i0 = max(0, int(round(s.start * sr)))
                i1 = i0 + len(audio)
                if i1 > len(mix):
                    mix = np.pad(mix, (0, i1 - len(mix)))
                mix[i0:i1] += audio
        all_words.extend(s.words)

    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix = (mix / peak * 0.98).astype(np.float32)

    final_master = proj.media_dir / "voice.wav"
    proj.media_dir.mkdir(parents=True, exist_ok=True)
    sf.write(str(final_master), mix, sr)
    proj.voice_file = "media/voice.wav"
    proj.words = sorted(all_words, key=lambda w: w.start)
    proj.save()
    return proj


def build_voiceover(proj: Project, segment_id: str | None = None, gap_s: float = 0.18) -> Project:
    """Tạo giọng đọc: hỗ trợ 1 đoạn riêng hoặc toàn bộ các đoạn voice_segments."""
    # Nếu chưa có segments mà có script cũ -> khởi tạo segment đầu tiên
    if not proj.voice_segments:
        if not (proj.script or "").strip():
            raise ValueError("Script trống.")
        proj.voice_segments = [
            VoiceSegment(
                text=proj.script,
                voice=proj.voice.voice,
                engine=proj.voice.engine,
                style=proj.voice.style,
                speed=proj.voice.speed,
                start=proj.voice.offset,
            )
        ]

    if segment_id:
        target_seg = next((s for s in proj.voice_segments if s.id == segment_id), None)
        if not target_seg:
            raise ValueError(f"Không tìm thấy đoạn thoại ID '{segment_id}'")
        build_single_segment(proj, target_seg, gap_s=gap_s)
    else:
        for seg in proj.voice_segments:
            if (seg.text or "").strip():
                build_single_segment(proj, seg, gap_s=gap_s)

    assemble_master_voice(proj)
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

