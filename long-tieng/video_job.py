#!/usr/bin/env python3
"""Lát A–E: job + ffmpeg tách tiếng/mux + wav STT."""
from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent
JOBS_DIR = ROOT / "jobs"
OUT_DIR = ROOT / "out"

VIDEO_EXTS = {".mp4", ".mov", ".mkv", ".webm", ".m4v", ".avi"}


def _ensure_dirs() -> None:
    JOBS_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)


def require_ffmpeg() -> tuple[str, str]:
    ffmpeg = shutil.which("ffmpeg")
    ffprobe = shutil.which("ffprobe")
    if not ffmpeg or not ffprobe:
        raise RuntimeError(
            "Chưa có ffmpeg. Cài rồi mở lại app:\n  brew install ffmpeg"
        )
    return ffmpeg, ffprobe


def _run_cmd(cmd: list[str], cwd: Path | None = None) -> str:
    try:
        proc = subprocess.run(cmd, check=True, capture_output=True, cwd=cwd)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Không chạy được lệnh: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace")[-800:]
        raise RuntimeError(f"{cmd[0]} lỗi:\n{err}") from exc
    return (proc.stderr or b"").decode("utf-8", errors="replace")


def new_job_id() -> str:
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    candidate = stamp
    n = 1
    while (JOBS_DIR / candidate).exists():
        n += 1
        candidate = f"{stamp}-{n}"
    return candidate


@dataclass
class Job:
    id: str
    dir: Path

    @property
    def source(self) -> Path:
        matches = sorted(self.dir.glob("source.*"))
        if not matches:
            raise RuntimeError(f"Job {self.id} chưa có source.")
        return matches[0]

    @property
    def audio_orig(self) -> Path:
        return self.dir / "audio_orig.wav"

    @property
    def audio_stt(self) -> Path:
        return self.dir / "audio_stt.wav"

    @property
    def orig_srt(self) -> Path:
        return self.dir / "orig.srt"

    @property
    def target_srt(self) -> Path:
        return self.dir / "target.srt"

    @property
    def final_srt(self) -> Path:
        return self.dir / "final.srt"

    @property
    def cues_dir(self) -> Path:
        return self.dir / "cues"

    @property
    def voice_new(self) -> Path:
        return self.dir / "voice_new.wav"

    @property
    def style_ass(self) -> Path:
        return self.dir / "style.ass"

    @property
    def preview_jpg(self) -> Path:
        return self.dir / "preview.jpg"

    @property
    def roundtrip(self) -> Path:
        return OUT_DIR / f"{self.id}_roundtrip.mp4"

    @property
    def final_mp4(self) -> Path:
        return OUT_DIR / f"{self.id}_final.mp4"


def job_from_id(job_id: str) -> Job:
    path = JOBS_DIR / job_id
    if not path.is_dir():
        raise RuntimeError(f"Không thấy job {job_id}.")
    return Job(id=job_id, dir=path)


def create_job(src: Path) -> Job:
    _ensure_dirs()
    if not src.exists():
        raise RuntimeError(f"Mất file: {src}")
    suffix = src.suffix.lower()
    if suffix not in VIDEO_EXTS:
        raise RuntimeError(
            f"Định dạng {suffix or 'không đuôi'} chưa nhận. "
            "Dùng mp4, mov, mkv, webm, m4v."
        )
    job_id = new_job_id()
    job = Job(id=job_id, dir=JOBS_DIR / job_id)
    job.dir.mkdir(parents=True, exist_ok=False)
    dest = job.dir / f"source{suffix}"
    shutil.copy2(src, dest)
    return job


def probe(path: Path) -> dict:
    _, ffprobe = require_ffmpeg()
    try:
        raw = subprocess.run(
            [
                ffprobe,
                "-v",
                "error",
                "-show_entries",
                "format=duration,size,format_name",
                "-show_entries",
                "stream=index,codec_type,codec_name,width,height,"
                "avg_frame_rate,channels,sample_rate",
                "-of",
                "json",
                str(path),
            ],
            check=True,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or "")[-800:]
        raise RuntimeError(f"ffprobe lỗi:\n{err}") from exc
    data = json.loads(raw.stdout or "{}")
    streams = data.get("streams") or []
    video = next((s for s in streams if s.get("codec_type") == "video"), None)
    audio = next((s for s in streams if s.get("codec_type") == "audio"), None)
    fmt = data.get("format") or {}
    duration = float(fmt.get("duration") or 0)
    info = {
        "duration": duration,
        "format": fmt.get("format_name") or "",
        "size": int(fmt.get("size") or 0),
        "has_video": video is not None,
        "has_audio": audio is not None,
        "width": int(video["width"]) if video and video.get("width") else 0,
        "height": int(video["height"]) if video and video.get("height") else 0,
        "fps": video.get("avg_frame_rate") if video else "",
        "v_codec": video.get("codec_name") if video else "",
        "a_codec": audio.get("codec_name") if audio else "",
        "channels": int(audio["channels"]) if audio and audio.get("channels") else 0,
        "sample_rate": int(audio["sample_rate"])
        if audio and audio.get("sample_rate")
        else 0,
    }
    if not info["has_video"]:
        raise RuntimeError("File không có luồng hình.")
    if not info["has_audio"]:
        raise RuntimeError("Video câm (không có tiếng). Không sang cửa 2.")
    return info


def format_probe(info: dict) -> str:
    w, h = info["width"], info["height"]
    dur = info["duration"]
    ch = info["channels"]
    sr = info["sample_rate"]
    return (
        f"{w}×{h} · {dur:.1f}s · {info['v_codec']}+{info['a_codec']} "
        f"· {ch}ch {sr} Hz"
    )


def extract_audio(job: Job) -> Path:
    ffmpeg, _ = require_ffmpeg()
    dest = job.audio_orig
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(job.source),
            "-vn",
            "-ac",
            "1",
            "-ar",
            "48000",
            str(dest),
        ]
    )
    if not dest.exists() or dest.stat().st_size < 1000:
        raise RuntimeError("Tách tiếng thất bại (file wav rỗng).")
    return dest


def ensure_stt_wav(job: Job) -> Path:
    """16 kHz mono — Whisper. Tái dùng nếu chưa cũ hơn audio_orig."""
    ffmpeg, _ = require_ffmpeg()
    if not job.audio_orig.exists():
        raise RuntimeError("Chưa có audio_orig.wav — tách tiếng trước.")
    dest = job.audio_stt
    if dest.exists() and dest.stat().st_mtime >= job.audio_orig.stat().st_mtime:
        return dest
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(job.audio_orig),
            "-ac",
            "1",
            "-ar",
            "16000",
            str(dest),
        ]
    )
    if not dest.exists() or dest.stat().st_size < 100:
        raise RuntimeError("Tạo audio_stt.wav thất bại.")
    return dest


def mux_original(job: Job) -> Path:
    ffmpeg, _ = require_ffmpeg()
    if not job.audio_orig.exists():
        raise RuntimeError("Chưa có audio_orig.wav — tách tiếng trước.")
    dest = job.roundtrip
    dest.parent.mkdir(parents=True, exist_ok=True)
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-i",
            str(job.source),
            "-i",
            str(job.audio_orig),
            "-map",
            "0:v:0",
            "-map",
            "1:a:0",
            "-c:v",
            "copy",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-shortest",
            str(dest),
        ]
    )
    if not dest.exists() or dest.stat().st_size < 1000:
        raise RuntimeError("Mux thất bại (mp4 rỗng).")
    return dest


def replace_source(job: Job, src: Path) -> Job:
    suffix = src.suffix.lower()
    if suffix not in VIDEO_EXTS:
        raise RuntimeError(
            f"Định dạng {suffix or 'không đuôi'} chưa nhận. "
            "Dùng mp4, mov, mkv, webm, m4v."
        )
    dest = job.dir / f"source{suffix}"
    for old in job.dir.glob("source.*"):
        if old.resolve() != dest.resolve():
            old.unlink(missing_ok=True)
    shutil.copy2(src, dest)
    return job


def ingest_and_roundtrip(
    src: Path, job_id: str | None = None
) -> tuple[Job, dict, Path, Path, bool]:
    """Cửa 1 + cửa 7 hẹp: copy job → tách wav → mux mp4 tiếng gốc."""
    require_ffmpeg()
    reused = False
    if (job_id or "").strip():
        try:
            job = job_from_id(job_id.strip())
            replace_source(job, src)
            reused = True
        except RuntimeError:
            job = create_job(src)
    else:
        job = create_job(src)
    info = probe(job.source)
    wav = extract_audio(job)
    mp4 = mux_original(job)
    return job, info, wav, mp4, reused
