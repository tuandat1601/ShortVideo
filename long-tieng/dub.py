#!/usr/bin/env python3
"""Lát D: atempo + volume + ghép cue theo timeline → voice_new.wav."""
from __future__ import annotations

from pathlib import Path
import shutil

from video_job import Job, _run_cmd, probe, require_ffmpeg

# Phong cách đọc = tốc độ mặc định + EQ/vang (ffmpeg). TTS vẫn VieNeu;
# style không đổi “cách nói” của model — chỉ hậu kỳ.
READ_STYLES: dict[str, dict] = {
    "Bình thường": {
        "speed": 1.00,
        "volume": 1.00,
        "hint": "Đọc đều, không hiệu ứng.",
        "pad_s": 0.0,
        "filters": [],
    },
    "Truyện ma": {
        "speed": 0.88,
        "volume": 1.12,
        "hint": "Chậm, rõ từng chữ, hơi vang ám ảnh.",
        "pad_s": 0.28,
        "filters": [
            "highpass=f=80",
            "treble=g=2",
            "bass=g=-1",
            "aecho=0.85:0.72:70:0.28",
            "aecho=0.8:0.65:210:0.16",
            "alimiter=limit=0.95",
        ],
    },
    "Tin tức": {
        "speed": 1.02,
        "volume": 1.10,
        "hint": "Rõ, gọn, hơi sáng — đọc tin / review.",
        "pad_s": 0.0,
        "filters": [
            "highpass=f=100",
            "treble=g=2.5",
            "alimiter=limit=0.95",
        ],
    },
    "Kể chuyện": {
        "speed": 0.93,
        "volume": 1.05,
        "hint": "Chậm ấm, dễ nghe dài.",
        "pad_s": 0.0,
        "filters": [
            "highpass=f=70",
            "bass=g=1.5",
            "treble=g=0.8",
        ],
    },
    "Devlog / Chill": {
        "speed": 0.95,
        "volume": 1.10,
        "hint": "Chậm rãi, ấm áp, mic cận thư thái như video indie dev / podcast.",
        "pad_s": 0.05,
        "filters": [
            "highpass=f=75",
            "bass=g=2.0",
            "treble=g=0.5",
            "alimiter=limit=0.95",
        ],
    },
    "Năng lượng": {
        "speed": 1.12,
        "volume": 1.15,
        "hint": "Nhanh, rõ, hơi bật — intro / hook.",
        "pad_s": 0.0,
        "filters": [
            "highpass=f=90",
            "treble=g=3",
            "alimiter=limit=0.95",
        ],
    },
}

DEFAULT_STYLE = "Bình thường"


def style_spec(name: str) -> dict:
    key = (name or "").strip()
    return READ_STYLES.get(key) or READ_STYLES[DEFAULT_STYLE]


def style_defaults(name: str) -> tuple[float, float, str]:
    spec = style_spec(name)
    return (
        float(spec["speed"]),
        float(spec["volume"]),
        str(spec["hint"]),
    )


def wav_seconds(path: Path) -> float:
    import soundfile as sf

    info = sf.info(str(path))
    if info.samplerate <= 0:
        return 0.0
    return float(info.frames) / float(info.samplerate)


def atempo_chain(speed: float) -> str:
    remaining = max(float(speed), 0.01)
    parts: list[str] = []
    while remaining > 2.0 + 1e-6:
        parts.append("atempo=2.0")
        remaining /= 2.0
    while remaining < 0.5 - 1e-6:
        parts.append("atempo=0.5")
        remaining /= 0.5
    parts.append(f"atempo={remaining:.5f}")
    return ",".join(parts)


def _speed_volume_af(speed: float, volume: float) -> str:
    user_speed = min(max(float(speed), 0.8), 1.25)
    vol = min(max(float(volume), 0.5), 2.0)
    return f"{atempo_chain(user_speed)},volume={vol:.4f}"


def apply_style_fx(src: Path, dest: Path, style: str) -> Path:
    """EQ / vang sau khi đã canh tốc độ. Pad chỉ để đuôi echo không bị cắt."""
    spec = style_spec(style)
    filters = list(spec.get("filters") or [])
    pad = float(spec.get("pad_s") or 0)
    if not filters and pad <= 0:
        if src.resolve() != dest.resolve():
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, dest)
        return dest
    ffmpeg, _ = require_ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    parts: list[str] = []
    if pad > 0:
        parts.append(f"apad=pad_dur={pad:.3f}")
    parts.extend(filters)
    tmp = dest if src.resolve() != dest.resolve() else dest.with_name(dest.stem + "_fx.wav")
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-af",
            ",".join(parts),
            str(tmp),
        ]
    )
    if tmp != dest:
        tmp.replace(dest)
    return dest


def apply_speed_volume(
    src: Path,
    dest: Path,
    speed: float,
    volume: float,
    style: str = DEFAULT_STYLE,
) -> Path:
    ffmpeg, _ = require_ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    timed = dest.with_name(dest.stem + "_spd.wav")
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-af",
            _speed_volume_af(speed, volume),
            str(timed),
        ]
    )
    apply_style_fx(timed, dest, style)
    timed.unlink(missing_ok=True)
    return dest


OVERLAP_S = 0.32
FIT_CAP = 1.35


def fit_cue_wav(
    src: Path,
    dest: Path,
    cue_dur: float,
    speed: float,
    volume: float,
    *,
    room: float | None = None,
    style: str = DEFAULT_STYLE,
) -> bool:
    """Canh cue. Trả True nếu wav dài hơn mốc SRT (tràn/overlap, không cắt đuôi)."""
    ffmpeg, _ = require_ffmpeg()
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_name(dest.stem + "_tmp.wav")
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(src),
            "-ac",
            "1",
            "-ar",
            "48000",
            "-af",
            _speed_volume_af(speed, volume),
            str(tmp),
        ]
    )
    dur = wav_seconds(tmp)
    window = max(float(cue_dur), 0.05)
    span = float(room) if room is not None else window + OVERLAP_S
    budget = max(window, min(span, window + OVERLAP_S))
    if dur > budget + 0.02:
        extra = min(dur / budget, FIT_CAP)
        fitted = dest.with_name(dest.stem + "_fit.wav")
        _run_cmd(
            [
                ffmpeg,
                "-y",
                "-i",
                str(tmp),
                "-af",
                atempo_chain(extra),
                "-ar",
                "48000",
                str(fitted),
            ]
        )
        tmp.unlink(missing_ok=True)
        tmp = fitted
        dur = wav_seconds(tmp)
    # FX (vang) sau khi canh — pad echo không đẩy atempo thêm.
    apply_style_fx(tmp, dest, style)
    tmp.unlink(missing_ok=True)
    speech = dur
    return speech > window + 0.08


def assemble_voice(
    job: Job, cue_wavs: list[tuple[float, float, Path]], total_dur: float | None = None
) -> Path:
    import numpy as np
    import soundfile as sf

    if total_dur is None:
        total_dur = probe(job.source)["duration"]
    sr = 48000
    n = max(int(round(float(total_dur) * sr)), sr)
    mix = np.zeros(n, dtype=np.float32)
    for start, end, path in cue_wavs:
        if not path.exists():
            continue
        audio, in_sr = sf.read(str(path), dtype="float32", always_2d=False)
        if getattr(audio, "ndim", 1) > 1:
            audio = audio.mean(axis=1)
        if int(in_sr) != sr:
            try:
                import soxr

                audio = soxr.resample(audio, int(in_sr), sr)
            except Exception:
                pass
        audio = np.asarray(audio, dtype=np.float32)
        i0 = max(int(round(start * sr)), 0)
        i1 = min(i0 + audio.shape[-1], n)
        if i0 >= n or i1 <= i0:
            continue
        sl = i1 - i0
        mix[i0:i1] += audio[:sl]
    peak = float(np.max(np.abs(mix))) if mix.size else 0.0
    if peak > 1.0:
        mix = (mix / peak * 0.99).astype(np.float32)
    dest = job.voice_new
    sf.write(str(dest), mix, sr)
    return dest
