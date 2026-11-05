#!/usr/bin/env python3
"""Lát B: faster-whisper local → orig.srt. Không gọi cloud."""
from __future__ import annotations

import os
import re
import threading

from video_job import Job, ensure_stt_wav

WHISPER_MODELS = ("tiny", "base", "small")
DEFAULT_MODEL = "small"
LANG_AUTO = "tự nhận"

_models: dict[tuple[str, str], object] = {}
_lock = threading.Lock()

_TS = re.compile(
    r"^(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})\s*-->\s*"
    r"(\d{1,2}):(\d{2}):(\d{2})[,.](\d{1,3})$"
)


def srt_timestamp(seconds: float) -> str:
    ms = max(int(round(float(seconds) * 1000)), 0)
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def _hms_to_sec(h: str, m: str, s: str, ms: str) -> float:
    milli = (ms + "000")[:3]
    return int(h) * 3600 + int(m) * 60 + int(s) + int(milli) / 1000


def segments_to_srt(rows: list[tuple[float, float, str]]) -> str:
    lines: list[str] = []
    n = 0
    for start, end, text in rows:
        cleaned = " ".join((text or "").split())
        if not cleaned:
            continue
        n += 1
        if end <= start:
            end = start + 0.2
        lines.append(str(n))
        lines.append(f"{srt_timestamp(start)} --> {srt_timestamp(end)}")
        lines.append(cleaned)
        lines.append("")
    return "\n".join(lines)


def parse_srt(
    raw: str, *, strict: bool = True
) -> list[tuple[float, float, str]]:
    text = (raw or "").replace("\r\n", "\n").replace("\r", "\n").strip()
    if not text:
        raise RuntimeError("SRT trống.")
    blocks = re.split(r"\n\s*\n", text)
    rows: list[tuple[float, float, str]] = []
    for block in blocks:
        lines = [ln.strip() for ln in block.split("\n") if ln.strip()]
        if not lines:
            continue
        if lines[0].isdigit():
            lines = lines[1:]
        if not lines:
            continue
        match = _TS.match(lines[0])
        if not match:
            if strict:
                raise RuntimeError(f"Sai mốc thời gian:\n{lines[0]}")
            continue
        start = _hms_to_sec(*match.group(1, 2, 3, 4))
        end = _hms_to_sec(*match.group(5, 6, 7, 8))
        body = " ".join(lines[1:]).strip()
        if not body:
            continue
        rows.append((start, end, body))
    if not rows:
        raise RuntimeError("SRT không có câu nào.")
    return rows


def get_whisper(model_name: str):
    name = (model_name or DEFAULT_MODEL).strip().lower()
    if name not in WHISPER_MODELS:
        raise RuntimeError(f"Model Whisper không hỗ trợ: {name}. Dùng tiny / base / small.")
    threads = max(int(os.cpu_count() or 4), 4)
    with _lock:
        for compute in ("int8", "float32"):
            hit = _models.get((name, compute))
            if hit is not None:
                return hit
        last: Exception | None = None
        for compute in ("int8", "float32"):
            try:
                from faster_whisper import WhisperModel

                print(
                    f"Load Whisper {name} ({compute}, {threads} thread) — "
                    "lần đầu sau mở app chậm ~15–40s…",
                    flush=True,
                )
                model = WhisperModel(
                    name,
                    device="cpu",
                    compute_type=compute,
                    cpu_threads=threads,
                    num_workers=1,
                )
                _models[(name, compute)] = model
                return model
            except Exception as exc:
                last = exc
        raise RuntimeError(
            "Không load được faster-whisper. Trong long-tieng:\n"
            "  pip install faster-whisper\n"
            "Lần đầu cần mạng để tải model.\n"
            f"Lỗi: {last}"
        ) from last


def preload_whisper(model_name: str = DEFAULT_MODEL) -> None:
    def _run() -> None:
        try:
            get_whisper(model_name)
        except Exception as exc:
            print(f"Preload Whisper lỗi: {exc}", flush=True)

    threading.Thread(target=_run, daemon=True, name="whisper-preload").start()


def transcribe_job(job: Job, model_name: str, language: str) -> tuple[str, str]:
    if not job.audio_orig.exists():
        raise RuntimeError("Chưa tách tiếng. Chạy cửa 1 trước.")
    wav = ensure_stt_wav(job)
    lang = None if not language or language.strip().lower() in {LANG_AUTO, "auto", ""} else language.strip().lower()
    model = get_whisper(model_name)
    segments, info = model.transcribe(
        str(wav),
        language=lang,
        vad_filter=False,
        beam_size=1,
        best_of=1,
        temperature=0.0,
        condition_on_previous_text=False,
    )
    rows: list[tuple[float, float, str]] = []
    for seg in segments:
        rows.append((float(seg.start), float(seg.end), seg.text or ""))
    srt = segments_to_srt(rows)
    if not srt.strip():
        raise RuntimeError("Không nhận ra lời nói. Thử model khác hoặc kiểm tra tiếng.")
    job.orig_srt.write_text(srt, encoding="utf-8")
    detected = getattr(info, "language", None) or lang or "?"
    note = (
        f"Job {job.id} · Whisper {model_name} · ngôn ngữ {detected} · "
        f"{len(parse_srt(srt))} câu → {job.orig_srt.name}"
    )
    return srt, note


def save_orig_srt(job: Job, raw: str) -> tuple[str, str]:
    rows = parse_srt(raw)
    srt = segments_to_srt(rows)
    job.orig_srt.write_text(srt, encoding="utf-8")
    if not job.final_srt.exists():
        job.target_srt.write_text(srt, encoding="utf-8")
    note = (
        f"Đã khóa {job.orig_srt.name} · {len(rows)} câu. "
        "Cửa 3: dán bản dịch rồi Dùng bản dán. "
        "Cùng ngôn ngữ: sang 4 Giọng (đọc bản gốc, không bắt khóa cửa 3)."
    )
    return srt, note
