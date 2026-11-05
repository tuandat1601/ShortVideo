#!/usr/bin/env python3
"""TTS local + tab Video (wizard cửa 1–7: STT → dịch → giọng → burn sub).

Chạy:
  cd long-tieng
  python3 -m venv .venv && source .venv/bin/activate
  pip install -r requirements.txt
  python app.py
→ http://127.0.0.1:7860
Cần ffmpeg (`brew install ffmpeg`).
"""
from __future__ import annotations

import re
import shutil
import subprocess
import threading
from datetime import datetime
from pathlib import Path

import gradio as gr

from burn import (
    DEFAULT_FONT,
    DEFAULT_FONT_SIZE,
    DEFAULT_TEXT_COLOR,
    PLACEHOLDER_HTML,
    PRESETS,
    available_fonts,
    export_final,
    extract_frame,
    cue_at,
    parse_layout,
    stage_html,
)
from dub import (
    DEFAULT_STYLE,
    READ_STYLES,
    apply_speed_volume,
    assemble_voice,
    fit_cue_wav,
    style_defaults,
)
from stt import (
    DEFAULT_MODEL,
    LANG_AUTO,
    WHISPER_MODELS,
    parse_srt,
    preload_whisper,
    save_orig_srt,
    transcribe_job,
)
from settings import (
    GEMINI_MODELS,
    OPENAI_MODELS,
    PROVIDERS,
    active_model,
    load_settings,
    save_settings,
    settings_summary,
)
from translate import (
    TARGET_LANGS,
    ensure_final_srt,
    list_gemini_models,
    list_ollama_models,
    list_openai_models,
    lock_final_srt,
    translate_cues,
)
from video_job import JOBS_DIR, format_probe, ingest_and_roundtrip, job_from_id

ROOT = Path(__file__).resolve().parent
PREVIEW_SAMPLE = (
    "Xin chào, đây là bản nghe thử. Tốc độ và âm lượng như thế này đã ổn chưa?"
)
VOICE_DIR = ROOT / "voice"
OUT_DIR = ROOT / "out"
CLIP_DIR = OUT_DIR / "_clips"
# VieNeu đọc trực tiếp wav/mp3/flac. Các đuôi còn lại đổi sang wav lúc thêm file.
CLONE_EXTS = {".wav", ".mp3", ".flac"}
AUDIO_EXTS = CLONE_EXTS | {
    ".m4a",
    ".aac",
    ".ogg",
    ".opus",
    ".wma",
    ".caf",
    ".aiff",
    ".aif",
    ".webm",
    ".mp4",
    ".mov",
    ".m4v",
}
UPLOAD_TYPES = ["audio", *sorted(AUDIO_EXTS)]
# VieNeu thiết kế clone ≤8s. Quét tối đa 2 phút để chọn đoạn rõ nhất.
MAX_REF_SECONDS = 8.0
SCAN_REF_SECONDS = 120.0
PRESET_PREFIX = "【sẵn】"
_enroll_cache: dict = {}

_engine = None
_engine_error: str | None = None
_lock = threading.Lock()


def _ensure_dirs() -> None:
    VOICE_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    CLIP_DIR.mkdir(parents=True, exist_ok=True)
    JOBS_DIR.mkdir(parents=True, exist_ok=True)


def list_file_voices() -> list[str]:
    _ensure_dirs()
    names = []
    for path in sorted(VOICE_DIR.iterdir()):
        if path.is_file() and path.suffix.lower() in AUDIO_EXTS:
            names.append(path.stem)
    return names


def list_preset_voice_ids() -> list[str]:
    if _engine is None:
        return []
    try:
        # list_preset_voices → [(label, voice_id), ...]
        return [voice_id for _label, voice_id in _engine.list_preset_voices()]
    except Exception:
        return []


def list_voice_choices() -> list[str]:
    import tts_en
    en_voices = tts_en.list_english_voice_choices() if tts_en.is_available() else []
    presets = [f"{PRESET_PREFIX}{name}" for name in list_preset_voice_ids()]
    return en_voices + presets + list_file_voices()


def voice_path(name: str) -> Path | None:
    if not name or name.startswith(PRESET_PREFIX) or name.startswith("【EN"):
        return None
    matches = [
        path
        for path in VOICE_DIR.iterdir()
        if path.is_file() and path.stem == name and path.suffix.lower() in AUDIO_EXTS
    ]
    if not matches:
        return None
    for ext in (".wav", ".mp3", ".flac"):
        for path in matches:
            if path.suffix.lower() == ext:
                return path
    return sorted(matches)[0]


def _unique_dest(path: Path) -> Path:
    if not path.exists():
        return path
    n = 1
    while True:
        candidate = path.with_name(f"{path.stem}_{n}{path.suffix}")
        if not candidate.exists():
            return candidate
        n += 1


def _run_cmd(cmd: list[str]) -> None:
    try:
        subprocess.run(cmd, check=True, capture_output=True)
    except FileNotFoundError as exc:
        raise RuntimeError(f"Không chạy được lệnh: {cmd[0]}") from exc
    except subprocess.CalledProcessError as exc:
        err = (exc.stderr or b"").decode("utf-8", errors="replace")[-500:]
        raise RuntimeError(f"{cmd[0]} lỗi:\n{err}") from exc


def _convert_to_wav(src: Path, dest: Path) -> None:
    dest.parent.mkdir(parents=True, exist_ok=True)
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg:
        _run_cmd(
            [ffmpeg, "-y", "-i", str(src), "-vn", "-ac", "1", "-ar", "44100", str(dest)]
        )
        return
    afconvert = shutil.which("afconvert")
    if afconvert:
        attempts = [
            [
                afconvert,
                "-f",
                "WAVE",
                "-d",
                "LEI16@44100",
                "-c",
                "1",
                str(src),
                str(dest),
            ],
            [afconvert, "-f", "WAVE", "-d", "LEI16", str(src), str(dest)],
        ]
        last_err: Exception | None = None
        for cmd in attempts:
            try:
                _run_cmd(cmd)
                return
            except RuntimeError as exc:
                last_err = exc
        if last_err and src.suffix.lower() in {".m4a", ".aac", ".caf", ".aiff", ".aif"}:
            raise last_err
    try:
        import soundfile as sf

        # Tránh librosa/numba cache lỗi trên một số môi trường.
        wav, sr = sf.read(str(src), dtype="float32", always_2d=False)
        if getattr(wav, "ndim", 1) > 1:
            wav = wav.mean(axis=1)
        if sr != 44100:
            try:
                import soxr

                wav = soxr.resample(wav, sr, 44100)
                sr = 44100
            except Exception:
                pass
        sf.write(str(dest), wav, int(sr))
    except Exception as exc:
        raise RuntimeError(
            f"Không đọc được {src.suffix or 'file này'}. "
            "Cài ffmpeg (`brew install ffmpeg`) rồi thêm lại."
        ) from exc


def prepare_ref(path: Path) -> Path:
    """Luôn về wav mono — mp3/flac raw dễ làm enroll lệch."""
    if path.suffix.lower() == ".wav":
        return path
    dest = CLIP_DIR / f"{path.stem}_full.wav"
    if not dest.exists() or dest.stat().st_mtime < path.stat().st_mtime:
        _convert_to_wav(path, dest)
    return dest


def _upload_path(item) -> Path:
    if isinstance(item, dict):
        raw = item.get("path") or item.get("name") or item.get("orig_name")
        return Path(str(raw))
    return Path(str(item))


def _video_upload_path(item) -> Path | None:
    if item is None:
        return None
    if isinstance(item, (list, tuple)):
        item = item[0] if item else None
        if item is None:
            return None
    if isinstance(item, dict):
        raw = item.get("video") or item.get("path") or item.get("name")
        return Path(str(raw)) if raw else None
    return Path(str(item))


def run_video_ingest(video, job_id: str | None = None) -> tuple:
    _ensure_dirs()
    empty = (None, None, None, "", "", "", None, PLACEHOLDER_HTML, None)
    src = _video_upload_path(video)
    if src is None:
        return empty + ("Chưa chọn video.",)
    if not src.exists():
        return empty + (f"Mất file tạm: {src}",)
    try:
        job, info, wav, mp4, reused = ingest_and_roundtrip(src, job_id)
    except Exception as exc:
        return empty + (str(exc),)
    orig = (
        job.orig_srt.read_text(encoding="utf-8") if job.orig_srt.exists() else ""
    )
    target = ""
    if job.final_srt.exists():
        target = job.final_srt.read_text(encoding="utf-8")
    elif job.target_srt.exists():
        target = job.target_srt.read_text(encoding="utf-8")
    keep = ""
    if reused:
        keep = " · giữ job cũ"
        if job.final_srt.exists():
            keep += " (đã có final.srt)"
        elif orig:
            keep += " (đã có orig.srt)"
    note = (
        f"Job {job.id}{keep} · {format_probe(info)}\n"
        f"Đã tách {wav.name} · mux tiếng gốc → {mp4.name}\n"
        + (
            "Sub cũ còn đó — cửa 3 Khóa / cửa 4 Giọng."
            if target or orig
            else "Tab 2 Sub: Lấy sub."
        )
    )
    return (
        str(wav),
        str(mp4),
        job.id,
        orig,
        orig,
        target,
        None,
        PLACEHOLDER_HTML,
        None,
        note,
    )


def run_transcribe(job_id: str, model_name: str, language: str) -> tuple:
    if not (job_id or "").strip():
        return "", "", "Chưa có job. Tab 1 Nhập trước."
    try:
        job = job_from_id(job_id.strip())
        srt, note = transcribe_job(job, model_name, language)
    except Exception as exc:
        return "", "", str(exc)
    return srt, srt, note


def run_lock_orig_srt(job_id: str, srt_text: str) -> tuple:
    if not (job_id or "").strip():
        return srt_text or "", srt_text or "", gr.update(), "Chưa có job."
    try:
        job = job_from_id(job_id.strip())
        srt, note = save_orig_srt(job, srt_text)
    except Exception as exc:
        return srt_text or "", srt_text or "", gr.update(), str(exc)
    # Không nhét orig vào ô dịch — để trống cho dán Gemini.
    return srt, srt, gr.update(), note


def _need_job(job_id: str):
    if not (job_id or "").strip():
        raise RuntimeError("Chưa có job. Cửa 1 trước.")
    return job_from_id(job_id.strip())


def on_provider_change(provider: str):
    cfg = load_settings()
    if provider == "Ollama":
        names = list_ollama_models() or ["(không có Ollama)"]
        model = cfg.get("ollama_model") or ""
        if model not in names:
            model = names[0]
        return (
            gr.update(choices=names, value=model),
            gr.update(value="", visible=False, label="API key"),
        )
    if provider == "OpenAI":
        names = list(OPENAI_MODELS)
        model = cfg.get("openai_model") or names[0]
        if model not in names:
            names = [model, *names]
        return (
            gr.update(choices=names, value=model),
            gr.update(
                value=cfg.get("openai_key") or "",
                visible=True,
                label="OpenAI API key",
            ),
        )
    names = list(GEMINI_MODELS)
    model = cfg.get("gemini_model") or names[0]
    if model not in names:
        names = [model, *names]
    return (
        gr.update(choices=names, value=model),
        gr.update(
            value=cfg.get("gemini_key") or "",
            visible=True,
            label="Gemini API key",
        ),
    )


def load_settings_form():
    cfg = load_settings()
    provider = cfg.get("provider") or "Gemini"
    model_upd, key_upd = on_provider_change(provider)
    summary = settings_summary(cfg)
    return provider, key_upd, model_upd, summary, summary


def refresh_cloud_models(provider: str, key: str):
    try:
        if provider == "Ollama":
            names = list_ollama_models() or ["(không có Ollama)"]
        elif provider == "OpenAI":
            names = list_openai_models(key)
        else:
            names = list_gemini_models(key)
        value = names[0] if names else None
        saved = active_model()
        if saved in names:
            value = saved
        return gr.update(choices=names, value=value), f"Đã tải {len(names)} model."
    except Exception as exc:
        return gr.update(), str(exc)


def save_settings_form(provider: str, key: str, model: str):
    try:
        if provider == "Ollama" and (model or "").startswith("("):
            raise RuntimeError("Ollama chưa có model. `ollama pull qwen2.5` hoặc chọn Gemini/OpenAI.")
        data = save_settings(provider, key, model)
        summary = settings_summary(data)
        return summary, summary
    except Exception as exc:
        return str(exc), settings_summary()


def run_translate(job_id: str, orig_text: str, target_lang: str):
    try:
        job = _need_job(job_id)
        orig = orig_text.strip() if orig_text else ""
        if not orig and job.orig_srt.exists():
            orig = job.orig_srt.read_text(encoding="utf-8")
        srt, used = translate_cues(orig, target_lang)
        srt, note = lock_final_srt(job, srt)
        return srt, f"{note} ({used})"
    except Exception as exc:
        return gr.update(), str(exc)


def run_use_pasted(job_id: str, target_text: str):
    try:
        job = _need_job(job_id)
        srt, note = ensure_final_srt(job, target_text)
        return srt, note
    except Exception as exc:
        return gr.update(), str(exc)


def run_load_trans_file(job_id: str, file_obj):
    try:
        if file_obj is None:
            raise RuntimeError("Chưa chọn file .srt / .txt.")
        path = _upload_path(file_obj)
        if not path.exists():
            raise RuntimeError(f"Mất file tạm: {path}")
        raw = path.read_text(encoding="utf-8")
        job = _need_job(job_id)
        srt, note = lock_final_srt(job, raw)
        return srt, note
    except Exception as exc:
        return gr.update(), str(exc)


def run_lock_final(job_id: str, target_text: str, draft: str = ""):
    try:
        job = _need_job(job_id)
        srt, note = ensure_final_srt(job, target_text or draft)
        return srt, note, _first_cue_text(srt)
    except Exception as exc:
        return target_text or "", str(exc), gr.update()


def run_autolock(job_id: str, target_text: str, draft: str):
    try:
        job = _need_job(job_id)
    except Exception as exc:
        return str(exc), gr.update()
    raw = (target_text or draft or "").strip()
    if not raw and not job.final_srt.exists() and not job.target_srt.exists():
        return (
            "Cửa 3: dán Gemini vào ô phải rồi bấm Dùng bản dán "
            "(khóa luôn). Ô Job trên thanh phải còn id.",
            gr.update(),
        )
    try:
        srt, note = ensure_final_srt(job, raw)
        return note, _first_cue_text(srt)
    except Exception as exc:
        return str(exc), gr.update()


def _first_cue_text(srt: str) -> str:
    try:
        rows = parse_srt(srt)
    except Exception:
        return PREVIEW_SAMPLE
    text = (rows[0][2] if rows else "").strip()
    if not text:
        return PREVIEW_SAMPLE
    if len(text) > 140:
        text = text[:140].rsplit(" ", 1)[0]
    return text


def apply_read_style(name: str):
    speed, volume, hint = style_defaults(name)
    return speed, volume, hint


def run_voice_preview(
    job_id: str,
    voice_name: str,
    consent: bool,
    speed: float,
    volume: float,
    preview_text: str,
    style: str = DEFAULT_STYLE,
):
    if not consent:
        return None, "Cần xác nhận: đây là giọng bạn hoặc bạn có quyền dùng."
    if not voice_name:
        return None, "Chọn giọng rồi Nghe thử."
    text = (preview_text or "").strip() or PREVIEW_SAMPLE
    if len(text) > 160:
        text = text[:160].rsplit(" ", 1)[0] or PREVIEW_SAMPLE
    base = OUT_DIR
    if (job_id or "").strip():
        try:
            base = _need_job(job_id).dir
        except Exception:
            base = OUT_DIR
    base.mkdir(parents=True, exist_ok=True)
    raw = base / "_preview_raw.wav"
    out = base / "_preview.wav"
    meta = base / "_preview_meta.txt"
    key = f"{voice_name}\n{text}"
    try:
        if not raw.exists() or meta.read_text(encoding="utf-8") != key:
            synthesize_to_wav(voice_name, text, raw)
            meta.write_text(key, encoding="utf-8")
        apply_speed_volume(raw, out, speed, volume, style=style)
        return (
            str(out),
            f"Nghe thử · {style} · tốc độ {speed:.2f} · âm lượng {volume:.2f}. "
            "Đổi slider / phong cách rồi bấm lại — không đọc TTS lần nữa.",
        )
    except Exception as exc:
        return None, str(exc)


def save_recorded_voice(audio_path: str | None, name: str | None):
    if not audio_path:
        return gr.update(), "Chưa có file ghi âm. Hãy bấm mic để thu trước."
    raw = (name or "").strip() or f"recorded_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
    clean = re.sub(r"[^\w\-]", "_", raw)
    dest = VOICE_DIR / f"{clean}.wav"
    try:
        _convert_to_wav(Path(audio_path), dest)
        choices = list_voice_choices()
        val = clean if clean in choices else (choices[0] if choices else None)
        return gr.update(choices=choices, value=val), f"Đã lưu: voice/{dest.name} (chọn được ngay)"
    except Exception as exc:
        return gr.update(), f"Lỗi lưu file: {exc}"


def synthesize_to_wav(voice_name: str, text: str, dest: Path) -> Path:
    cleaned = (text or "").strip()
    if not cleaned:
        raise RuntimeError("Câu trống, bỏ qua.")
    dest.parent.mkdir(parents=True, exist_ok=True)
    if voice_name.startswith("【EN"):
        import tts_en
        tts_en.synthesize_english(cleaned, voice_name, dest)
    elif voice_name.startswith(PRESET_PREFIX):
        audio, tts, _, _ = synthesize_preset(cleaned, voice_name[len(PRESET_PREFIX) :])
        tts.save(audio, str(dest))
    else:
        src = voice_path(voice_name)
        if src is None:
            raise RuntimeError(f"Không thấy file giọng '{voice_name}'.")
        ref = prepare_ref(src)
        audio, tts, _, _, _ = synthesize_clone(cleaned, ref)
        tts.save(audio, str(dest))
    return dest


def run_dub(
    job_id: str,
    voice_name: str,
    consent: bool,
    speed: float,
    volume: float,
    target_text: str = "",
    draft: str = "",
    style: str = DEFAULT_STYLE,
):
    if not consent:
        yield None, "Cần xác nhận: đây là giọng bạn hoặc bạn có quyền dùng."
        return
    if not voice_name:
        yield None, "Chọn giọng (sẵn hoặc file voice/)."
        return
    try:
        job = _need_job(job_id)
        srt, note = ensure_final_srt(job, target_text or draft)
        rows = parse_srt(srt)
        n = len(rows)
        yield (
            None,
            f"Đọc {n} câu từng mốc SRT (không đọc cả bài một lượt). "
            "Câu 1 khớp 0–2.4s, câu 2 khớp 2.4–3.8s, …",
        )
        job.cues_dir.mkdir(parents=True, exist_ok=True)
        cue_wavs: list[tuple[float, float, Path]] = []
        keep: set[str] = set()
        reused = 0
        spilled: list[str] = []
        for i, (start, end, text) in enumerate(rows, 1):
            snippet = " ".join((text or "").split())
            yield None, f"Đọc {i}/{n} · {snippet[:52] or '(trống)'}"
            raw = job.cues_dir / f"{i:04d}_raw.wav"
            fitted = job.cues_dir / f"{i:04d}.wav"
            key_path = raw.with_suffix(".key")
            keep.update({raw.name, fitted.name, key_path.name})
            if not snippet:
                continue
            key = f"{voice_name}\n{snippet}"
            if (
                raw.exists()
                and key_path.exists()
                and key_path.read_text(encoding="utf-8") == key
            ):
                reused += 1
            else:
                synthesize_to_wav(voice_name, snippet, raw)
                key_path.write_text(key, encoding="utf-8")
            nxt = rows[i][0] if i < n else end + 0.5
            room = max(end, nxt) - start
            if fit_cue_wav(
                raw, fitted, end - start, speed, volume, room=room, style=style
            ):
                spilled.append(str(i))
            cue_wavs.append((start, end, fitted))
        for leftover in job.cues_dir.iterdir():
            if leftover.is_file() and leftover.name not in keep:
                leftover.unlink(missing_ok=True)
        out = assemble_voice(job, cue_wavs)
        extra = f" · tái sử dụng {reused} câu" if reused else ""
        spill = ""
        if spilled:
            shown = ",".join(spilled[:12])
            more = f" +{len(spilled) - 12}" if len(spilled) > 12 else ""
            spill = f" · câu {shown}{more} dài hơn mốc (tràn nhẹ, không cắt chữ)"
        yield (
            str(out),
            f"Đã đọc {len(cue_wavs)}/{n} câu · {style}{extra}{spill} → {out.name}. Sang cửa 6.",
        )
    except Exception as exc:
        yield None, str(exc)


def _pos_label(x: float, y: float, w: float = 70.0) -> str:
    return f"{x:.0f}% × {y:.0f}% · rộng {w:.0f}%"


def apply_pos_preset(
    name: str,
    state: dict | None,
    bg: bool,
    bg_color: str,
    box_w: float,
    bg_opacity: float,
    text_color: str,
    font_name: str,
    font_size: float,
):
    x, y = PRESETS.get(name) or PRESETS["Dưới"]
    html = _restyle(
        state,
        x,
        y,
        bg,
        bg_color,
        box_w,
        bg_opacity,
        text_color,
        font_name,
        font_size,
    )
    return x, y, _pos_label(x, y, box_w), html


def apply_drag(evt: gr.EventData):
    raw = ""
    data = getattr(evt, "_data", None)
    if isinstance(data, dict):
        raw = str(data.get("layout") or "")
    elif data:
        raw = str(data)
    if not raw:
        try:
            raw = str(evt.layout)
        except AttributeError:
            raw = ""
    x, y, w = parse_layout(raw)
    return x, y, w, _pos_label(x, y, w)


def _restyle(
    state: dict | None,
    x_pct: float,
    y_pct: float,
    bg: bool,
    bg_color: str,
    box_w: float = 70.0,
    bg_opacity: float = 95.0,
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: float = DEFAULT_FONT_SIZE,
):
    if not state or not state.get("frame"):
        return PLACEHOLDER_HTML
    return stage_html(
        Path(state["frame"]),
        state.get("text") or "",
        x_pct,
        y_pct,
        bool(bg),
        bg_color or "#000000",
        box_w,
        bg_opacity,
        text_color=text_color or DEFAULT_TEXT_COLOR,
        font_name=font_name or DEFAULT_FONT,
        font_size=font_size,
    )


def restyle_preview(
    state: dict | None,
    x_pct: float,
    y_pct: float,
    bg: bool,
    bg_color: str,
    box_w: float,
    bg_opacity: float,
    text_color: str,
    font_name: str,
    font_size: float,
):
    return _restyle(
        state,
        x_pct,
        y_pct,
        bg,
        bg_color,
        box_w,
        bg_opacity,
        text_color,
        font_name,
        font_size,
    )


def run_preview(
    job_id: str,
    x_pct: float,
    y_pct: float,
    at_sec: float,
    bg: bool,
    bg_color: str,
    box_w: float,
    bg_opacity: float,
    text_color: str,
    font_name: str,
    font_size: float,
):
    try:
        job = _need_job(job_id)
        frame, used = extract_frame(job, at_sec)
        text = cue_at(job, used)
        state = {"frame": str(frame), "text": text}
        html = stage_html(
            frame,
            text,
            x_pct,
            y_pct,
            bool(bg),
            bg_color or "#000000",
            box_w,
            bg_opacity,
            text_color=text_color or DEFAULT_TEXT_COLOR,
            font_name=font_name or DEFAULT_FONT,
            font_size=font_size,
        )
        return (
            html,
            state,
            f"Kéo ô chữ trên khung (không kéo Mp4 cuối) · {_pos_label(x_pct, y_pct, box_w)}.",
        )
    except Exception as exc:
        return PLACEHOLDER_HTML, None, str(exc)


def run_export(
    job_id: str,
    x_pct: float,
    y_pct: float,
    bg: bool,
    bg_color: str,
    box_w: float,
    bg_opacity: float,
    text_color: str,
    font_name: str,
    font_size: float,
):
    try:
        job = _need_job(job_id)
        mp4 = export_final(
            job,
            x_pct,
            y_pct,
            bg=bool(bg),
            bg_color=bg_color or "#000000",
            text_color=text_color or DEFAULT_TEXT_COLOR,
            font_name=font_name or DEFAULT_FONT,
            font_size=int(font_size) if font_size is not None else None,
            box_w_pct=box_w,
            bg_opacity=bg_opacity,
        )
        extra = " · có nền" if bg else ""
        return (
            str(mp4),
            f"Xong → {mp4.name} (sub burn{extra} · {font_name or DEFAULT_FONT} "
            f"{int(font_size or DEFAULT_FONT_SIZE)}px · giọng mới).",
        )
    except Exception as exc:
        return None, str(exc)


def import_voice(src: Path) -> Path:
    suffix = src.suffix.lower()
    if suffix in CLONE_EXTS:
        dest = _unique_dest(VOICE_DIR / src.name)
        shutil.copy2(src, dest)
        return dest
    dest = _unique_dest(VOICE_DIR / f"{src.stem}.wav")
    _convert_to_wav(src, dest)
    return dest


def add_voice_file(upload) -> tuple:
    _ensure_dirs()
    if upload is None:
        return refresh_dropdown(), "Chưa chọn file."
    raw = upload if isinstance(upload, list) else [upload]
    saved: list[str] = []
    errors: list[str] = []
    converted: list[str] = []
    last_stem: str | None = None
    for item in raw:
        src = _upload_path(item)
        if not src.exists():
            errors.append(f"Mất file tạm: {src.name}")
            continue
        try:
            dest = import_voice(src)
        except Exception as exc:
            errors.append(f"{src.name}: {exc}")
            continue
        saved.append(dest.name)
        last_stem = dest.stem
        if src.suffix.lower() not in CLONE_EXTS:
            converted.append(src.suffix.lower() or src.name)
    parts = []
    if saved:
        parts.append("Đã lưu: " + ", ".join(saved))
        if converted:
            parts.append("(đã đổi sang wav: " + ", ".join(converted) + ")")
    if errors:
        parts.append("Lỗi: " + " | ".join(errors))
    if not saved:
        return refresh_dropdown(), parts[-1] if parts else "Không thêm được file."
    return refresh_dropdown(last_stem), " ".join(parts)


def get_engine():
    global _engine, _engine_error
    if _engine is not None:
        return _engine
    with _lock:
        if _engine is not None:
            return _engine
        try:
            from vieneu import Vieneu

            # Mac thường rơi ONNX/CPU: fp32 rõ hơn int8 (chậm hơn một chút).
            # Có MPS thì thử PyTorch trước.
            kwargs = {}
            try:
                import torch

                if torch.backends.mps.is_available():
                    kwargs = {"backend": "pytorch", "device": "mps"}
                else:
                    kwargs = {"precision": "fp32"}
            except Exception:
                kwargs = {"precision": "fp32"}

            try:
                _engine = Vieneu(**kwargs)
            except Exception:
                _engine = Vieneu(precision="fp32")
            _engine_error = None
            return _engine
        except Exception as exc:
            _engine_error = str(exc)
            raise RuntimeError(
                "Không load được VieNeu. Trong thư mục long-tieng:\n"
                "  python3 -m venv .venv && source .venv/bin/activate\n"
                "  pip install -r requirements.txt\n\n"
                f"Lỗi: {exc}"
            ) from exc


def _load_ref_wav(path: Path):
    import numpy as np
    import soundfile as sf

    wav, sr = sf.read(str(path), dtype="float32", always_2d=False)
    if getattr(wav, "ndim", 1) > 1:
        wav = wav.mean(axis=1)
    wav = np.asarray(wav, dtype=np.float32)
    try:
        import librosa

        wav, _ = librosa.effects.trim(wav, top_db=30)
    except Exception:
        nonzero = np.flatnonzero(np.abs(wav) > 1e-5)
        if nonzero.size:
            wav = wav[
                max(int(nonzero[0]) - int(0.01 * sr), 0) : min(
                    int(nonzero[-1]) + int(0.01 * sr), len(wav)
                )
            ]
    cap = int(SCAN_REF_SECONDS * sr)
    if wav.shape[-1] > cap:
        wav = wav[:cap]
    duration = float(wav.shape[-1]) / float(sr)
    return wav, int(sr), duration


def _best_speech_window(wav, sr: int, seconds: float):
    """Lấy đoạn năng lượng cao nhất trong file (tránh đầu/cuối im hoặc nhạc)."""
    import numpy as np

    win = max(int(seconds * sr), sr)
    if wav.shape[-1] <= win:
        return wav
    step = max(int(0.25 * sr), 1)
    best_i, best_e = 0, -1.0
    for start in range(0, wav.shape[-1] - win + 1, step):
        chunk = wav[start : start + win]
        e = float(np.sqrt(np.mean(np.square(chunk))))
        if e > best_e:
            best_e, best_i = e, start
    return wav[best_i : best_i + win]


def _peak_normalize(wav, peak: float = 0.9):
    import numpy as np

    m = float(np.max(np.abs(wav))) if wav.size else 0.0
    if m < 1e-6:
        return wav
    return (wav * (peak / m)).astype(np.float32)


def make_clone_clip(path: Path) -> tuple[Path, float, float]:
    """Xuất đúng 1 file wav ≤8s mà VieNeu sẽ enroll (nghe thử được)."""
    import soundfile as sf

    key = (str(path.resolve()), path.stat().st_mtime_ns, MAX_REF_SECONDS)
    hit = _enroll_cache.get(("clip",) + key)
    if hit is not None:
        return hit

    wav, sr, file_duration = _load_ref_wav(path)
    wav = _best_speech_window(wav, sr, MAX_REF_SECONDS)
    wav = _peak_normalize(wav)
    used = float(wav.shape[-1]) / float(sr)
    dest = CLIP_DIR / f"{path.stem}_clone8s.wav"
    sf.write(str(dest), wav, sr)
    packed = (dest, file_duration, used)
    _enroll_cache[("clip",) + key] = packed
    return packed


def synthesize_preset(text: str, preset_name: str):
    tts = get_engine()
    audio = tts.infer(
        text,
        voice=preset_name,
        temperature=0.55,
        top_k=20,
        top_p=0.9,
        repetition_penalty=1.3,
        apply_watermark=False,
    )
    return audio, tts, None, None


def synthesize_clone(text: str, ref: Path):
    tts = get_engine()
    clip, file_duration, used = make_clone_clip(ref)
    errors: list[str] = []
    # Ưu tiên denoise; thất bại thì không denoise. Nhiệt độ thấp → ít “đớ/rên” hơn.
    for denoise in (True, False):
        try:
            audio = tts.infer(
                text,
                ref_audio=str(clip),
                denoise=denoise,
                use_ref_codes=True,
                temperature=0.55,
                top_k=20,
                top_p=0.9,
                repetition_penalty=1.3,
                apply_watermark=False,
            )
            return audio, tts, file_duration, used, clip
        except Exception as exc:
            errors.append(f"denoise={denoise}: {exc}")
    raise RuntimeError(
        "Clone giọng thất bại. VieNeu chỉ dùng ~8s đoạn nói rõ nhất.\n"
        + "\n".join(errors)
    )


def refresh_dropdown(selected: str | None = None):
    try:
        get_engine()  # lần đầu: hiện thêm 【sẵn】…
    except Exception:
        pass
    names = list_voice_choices()
    value = selected if selected in names else (names[0] if names else None)
    return gr.update(choices=names, value=value)


def generate(voice_name: str, text: str, consent: bool, style: str = DEFAULT_STYLE):
    _ensure_dirs()
    if not consent:
        return None, None, "Cần xác nhận: đây là giọng bạn hoặc bạn có quyền dùng."
    if not voice_name:
        return None, None, "Thêm file vào voice/ hoặc chọn giọng sẵn, rồi Đọc."
    cleaned = (text or "").strip()
    if not cleaned:
        return None, None, "Nhập đoạn text cần đọc."

    try:
        if voice_name.startswith("【EN"):
            clip_path = None
            note = f"Kokoro English ({voice_name})"
            audio = None
            tts = None
        elif voice_name.startswith(PRESET_PREFIX):
            preset = voice_name[len(PRESET_PREFIX) :]
            audio, tts, _, _ = synthesize_preset(cleaned, preset)
            clip_path = None
            note = f"giọng sẵn '{preset}' (ổn định hơn clone)"
        else:
            src = voice_path(voice_name)
            if src is None:
                return None, None, f"Không thấy file giọng '{voice_name}'."
            ref = prepare_ref(src)
            audio, tts, file_duration, used, clip = synthesize_clone(cleaned, ref)
            clip_path = str(clip)
            note = (
                f"file {file_duration:.0f}s → clone {used:.1f}s "
                f"(zero-shot, không y chang 100%)"
            )
    except Exception as exc:
        return None, None, str(exc)

    stamp = datetime.now().strftime("%H%M%S")
    safe = re.sub(r"[^\w\-]", "_", voice_name)
    raw = OUT_DIR / f"{safe}_{stamp}_raw.wav"
    dest = OUT_DIR / f"{safe}_{stamp}.wav"
    if voice_name.startswith("【EN"):
        import tts_en
        tts_en.synthesize_english(cleaned, voice_name, raw)
    else:
        tts.save(audio, str(raw))
    spd, vol, _ = style_defaults(style)
    apply_speed_volume(raw, dest, spd, vol, style=style)
    raw.unlink(missing_ok=True)
    return str(dest), clip_path, f"Xong → {dest.name} · {style} · {note}"


NAV_KEYS = (
    "video",
    "sub",
    "translate",
    "voice",
    "export",
    "tts",
    "settings",
)


def _switch_nav(selected: str):
    panels = [gr.update(visible=(key == selected)) for key in NAV_KEYS]
    buttons = [
        gr.update(variant="primary" if key == selected else "secondary")
        for key in NAV_KEYS
    ]
    return (*panels, *buttons)


CSS = """
:root, .gradio-container, .dark {
  --body-background-fill: #0e0e10 !important;
  --background-fill-primary: #16161a !important;
  --background-fill-secondary: #1c1c22 !important;
  --block-background-fill: #1a1a1f !important;
  --border-color-primary: #2c2c34 !important;
  --body-text-color: #ececec !important;
  --color-accent: #00d4c8 !important;
  --button-primary-background-fill: #00d4c8 !important;
  --button-primary-background-fill-hover: #5aeee4 !important;
  --button-primary-text-color: #0b0b0b !important;
  --button-primary-text-color-hover: #0b0b0b !important;
  --input-background-fill: #121216 !important;
}
.gradio-container {
  max-width: 100% !important;
  padding: 0 !important;
  background: #0e0e10 !important;
}
footer, .footer { display: none !important; }
#topbar {
  background: #111114;
  border-bottom: 1px solid #2a2a30;
  padding: 10px 16px 6px;
  margin: 0 !important;
}
#topbar .prose { color: #f2f2f2; }
#app-nav {
  display: flex !important;
  flex-wrap: wrap !important;
  gap: 8px !important;
  padding: 10px 16px !important;
  margin: 0 !important;
  background: #141418;
  border-bottom: 1px solid #2a2a30;
}
#app-nav button {
  flex: 1 1 96px !important;
  min-width: 96px !important;
  font-weight: 700 !important;
}
#app-body {
  padding: 16px 20px 24px !important;
}
.panel-title { margin: 0 0 12px 0 !important; color: #fff !important; }
.sub-stage {
  position: relative;
  width: 100%;
  user-select: none;
  cursor: default;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  min-height: 180px;
  touch-action: none;
}
.sub-stage.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  color: #9a9aa3;
  cursor: default;
  background: #16161a;
}
.sub-stage img {
  width: 100%;
  height: auto;
  display: block;
  pointer-events: none;
  user-select: none;
}
.sub-box {
  position: absolute;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #fff;
  font-weight: 700;
  font-size: clamp(14px, 2.1vw, 28px);
  line-height: 1.35;
  text-shadow: 0 0 4px #000, 0 1px 2px #000;
  pointer-events: auto;
  cursor: grab;
  padding: 10px 18px;
  border-radius: 10px;
  white-space: normal;
  box-sizing: border-box;
  outline: 2px dashed #00d4c8;
  z-index: 2;
}
.sub-box:active { cursor: grabbing; }
.sub-handle {
  position: absolute;
  top: 18%;
  bottom: 18%;
  width: 10px;
  background: #00d4c8;
  border-radius: 6px;
  cursor: ew-resize;
  z-index: 3;
}
.sub-handle-w { left: -5px; }
.sub-handle-e { right: -5px; }
"""

THEME = gr.themes.Default(
    primary_hue="teal",
    secondary_hue="zinc",
    neutral_hue="zinc",
    font=[gr.themes.GoogleFont("DM Sans"), "ui-sans-serif", "system-ui"],
)

SUB_STAGE_CSS = """
.sub-stage {
  position: relative;
  width: 100%;
  user-select: none;
  cursor: default;
  background: #000;
  border-radius: 10px;
  overflow: hidden;
  min-height: 180px;
  touch-action: none;
}
.sub-stage.empty {
  display: flex;
  align-items: center;
  justify-content: center;
  min-height: 280px;
  color: #9a9aa3;
  cursor: default;
  background: #16161a;
}
.sub-stage img {
  width: 100%;
  height: auto;
  display: block;
  pointer-events: none;
  user-select: none;
}
.sub-box {
  position: absolute;
  transform: translate(-50%, -50%);
  text-align: center;
  color: #fff;
  font-weight: 700;
  font-size: clamp(14px, 2.1vw, 28px);
  line-height: 1.35;
  text-shadow: 0 0 4px #000, 0 1px 2px #000;
  pointer-events: auto;
  cursor: grab;
  padding: 10px 18px;
  border-radius: 10px;
  white-space: normal;
  box-sizing: border-box;
  outline: 2px dashed #00d4c8;
  z-index: 2;
}
.sub-box:active { cursor: grabbing; }
.sub-handle {
  position: absolute;
  top: 18%;
  bottom: 18%;
  width: 10px;
  background: #00d4c8;
  border-radius: 6px;
  cursor: ew-resize;
  z-index: 3;
}
.sub-handle-w { left: -5px; }
.sub-handle-e { right: -5px; }
"""

SUB_DRAG_ONLOAD = """
if (element.dataset.subDragBound !== "1") {
  element.dataset.subDragBound = "1";
  let mode = null;
  let grabDx = 0;
  let grabDy = 0;
  const boxEl = () => element.querySelector(".sub-box");
  const stageEl = () => element.querySelector(".sub-stage");
  const rectOf = (stage) => {
    const img = stage.querySelector("img");
    return (img || stage).getBoundingClientRect();
  };
  const pct = (stage, ev) => {
    const r = rectOf(stage);
    if (r.width < 2 || r.height < 2) return [50, 50];
    const x = ((ev.clientX - r.left) / r.width) * 100;
    const y = ((ev.clientY - r.top) / r.height) * 100;
    return [x, y];
  };
  const applyMove = (stage, ev) => {
    const box = boxEl();
    if (!box) return;
    const [x, y] = pct(stage, ev);
    box.style.left = Math.min(95, Math.max(5, x - grabDx)).toFixed(1) + "%";
    box.style.top = Math.min(95, Math.max(5, y - grabDy)).toFixed(1) + "%";
  };
  const applyResize = (stage, ev) => {
    const box = boxEl();
    if (!box) return;
    const r = rectOf(stage);
    const px = ((ev.clientX - r.left) / r.width) * 100;
    const cx = parseFloat(box.style.left) || 50;
    let w = Math.abs(px - cx) * 2;
    w = Math.min(92, Math.max(30, w));
    box.style.width = w.toFixed(1) + "%";
  };
  const commit = () => {
    const box = boxEl();
    if (!box) return;
    const x = parseFloat(box.style.left) || 50;
    const y = parseFloat(box.style.top) || 88;
    const w = parseFloat(box.style.width) || 70;
    trigger("click", { layout: x + "," + y + "," + w });
  };
  element.addEventListener("pointerdown", (ev) => {
    const stage = stageEl();
    if (!stage || stage.classList.contains("empty") || !stage.querySelector("img")) return;
    const path = ev.composedPath ? ev.composedPath() : [];
    const inStage = path.includes(stage) || stage.contains(ev.target);
    if (!inStage) return;
    const t = ev.target;
    const handle = t && t.closest ? t.closest(".sub-handle") : null;
    const box = boxEl();
    if (handle) {
      mode = "resize";
    } else if (box && (t === box || (t.closest && t.closest(".sub-box")))) {
      mode = "move";
      const [px, py] = pct(stage, ev);
      grabDx = px - (parseFloat(box.style.left) || 50);
      grabDy = py - (parseFloat(box.style.top) || 88);
    } else {
      mode = "move";
      grabDx = 0;
      grabDy = 0;
      applyMove(stage, ev);
    }
    ev.preventDefault();
    try { element.setPointerCapture(ev.pointerId); } catch (e) {}
  });
  element.addEventListener("pointermove", (ev) => {
    if (!mode) return;
    const stage = stageEl();
    if (!stage) return;
    if (mode === "resize") applyResize(stage, ev);
    else applyMove(stage, ev);
  });
  const endDrag = () => {
    if (!mode) return;
    mode = null;
    commit();
  };
  element.addEventListener("pointerup", endDrag);
  element.addEventListener("pointercancel", endDrag);
}
"""

with gr.Blocks(
    title="Studio lồng tiếng",
    theme=THEME,
    fill_height=True,
    fill_width=True,
    css=CSS,
) as demo:
    with gr.Row(elem_id="topbar"):
        gr.Markdown("**STUDIO**  lồng tiếng / sub")
        engine_line = gr.Textbox(
            label="Máy dịch",
            interactive=False,
            value=settings_summary(),
            scale=2,
        )
        job_id_box = gr.Textbox(label="Job", interactive=False, scale=1)
        video_status = gr.Textbox(label="Trạng thái", interactive=False, scale=2)
        draft_srt = gr.State("")

    with gr.Row(elem_id="app-nav"):
        nav_video = gr.Button("1 Video", variant="primary")
        nav_sub = gr.Button("2 Sub", variant="secondary")
        nav_translate = gr.Button("3 Dịch", variant="secondary")
        nav_voice = gr.Button("4 Giọng", variant="secondary")
        nav_export = gr.Button("5 Xuất", variant="secondary")
        nav_tts = gr.Button("TTS", variant="secondary")
        nav_settings = gr.Button("Cài đặt", variant="secondary")

    with gr.Column(elem_id="app-body"):
        with gr.Column(visible=True) as panel_video:
            gr.Markdown("### Nhập video", elem_classes=["panel-title"])
            with gr.Row(equal_height=True):
                with gr.Column(scale=2, min_width=280):
                    video_in = gr.Video(
                        label="Kéo thả mp4 / mov",
                        sources=["upload"],
                        include_audio=True,
                        height=320,
                    )
                    ingest = gr.Button("Tách tiếng + ghép lại", variant="primary")
                    wav_out = gr.Audio(label="Tiếng đã tách", type="filepath")
                with gr.Column(scale=3, min_width=360):
                    video_out = gr.Video(
                        label="Xem trước (tiếng gốc)",
                        interactive=False,
                        height=420,
                    )

        with gr.Column(visible=False) as panel_sub:
            gr.Markdown("### Lấy phụ đề", elem_classes=["panel-title"])
            with gr.Row(equal_height=True):
                with gr.Column(scale=1, min_width=240):
                    stt_model = gr.Dropdown(
                        label="Whisper",
                        choices=list(WHISPER_MODELS),
                        value=DEFAULT_MODEL,
                    )
                    stt_lang = gr.Dropdown(
                        label="Ngôn ngữ gốc",
                        choices=[LANG_AUTO, "vi", "en", "zh", "ja", "ko"],
                        value=LANG_AUTO,
                    )
                    transcribe_btn = gr.Button("Lấy sub", variant="primary")
                    lock_srt_btn = gr.Button("Dùng bản sub này")
                with gr.Column(scale=3, min_width=360):
                    srt_box = gr.Textbox(
                        label="orig.srt — sửa tay",
                        lines=22,
                        placeholder="Nhập video xong bấm Lấy sub.",
                    )

        with gr.Column(visible=False) as panel_translate:
            gr.Markdown(
                "### Dịch & khóa bản đọc\n"
                "**Nhanh:** copy ô trái → Gemini chat → dán ô phải → **Dùng bản dán** "
                "(khóa luôn, lệch số câu thì ghép mốc gốc).\n"
                "Đã khóa sub cửa 2: sang **4 Giọng** đọc bản gốc — không bắt khóa cửa 3. "
                "Nút Dịch = API trong app.",
                elem_classes=["panel-title"],
            )
            with gr.Row():
                target_lang = gr.Dropdown(
                    label="Dịch sang",
                    choices=list(TARGET_LANGS),
                    value="vi",
                    scale=1,
                )
                translate_btn = gr.Button("Dịch (API)", variant="secondary", scale=1)
                paste_btn = gr.Button("Dùng bản dán", variant="primary", scale=1)
                lock_final_btn = gr.Button("Khóa bản đọc", scale=1)
            trans_file = gr.File(
                label="Hoặc gửi file đã dịch (.srt / .txt)",
                file_types=[".srt", ".txt"],
                type="filepath",
            )
            with gr.Row(equal_height=True):
                srt_view = gr.Textbox(
                    label="Gốc — copy đưa Gemini",
                    lines=20,
                    interactive=False,
                    buttons=["copy"],
                )
                target_box = gr.Textbox(
                    label="Bản dịch — dán từ Gemini / chat",
                    lines=20,
                    placeholder="Dán SRT hoặc từng câu (cùng số câu với gốc), rồi bấm Dùng bản dán.",
                    buttons=["copy"],
                )

        with gr.Column(visible=False) as panel_voice:
            gr.Markdown(
                "### Nhét giọng\n"
                "**Đọc + ghép** = TTS **từng câu sub** cho khớp timestamp "
                "(file bạn ~149 câu ≈ 149 lần đọc, vài phút). "
                "Không đọc cả bài một lượt — nếu làm vậy sẽ lệch miệng/sub. "
                "Chọn **phong cách đọc** (vd. Truyện ma = chậm, rõ, hơi vang) rồi Nghe thử. "
                "Xem ô Trạng thái: `Đọc 12/149`.",
                elem_classes=["panel-title"],
            )
            with gr.Row(equal_height=True):
                with gr.Column(scale=2, min_width=260):
                    video_voice = gr.Dropdown(
                        label="Giọng",
                        choices=list_voice_choices(),
                        value=(
                            list_voice_choices()[0] if list_voice_choices() else None
                        ),
                    )
                    video_voice_refresh = gr.Button("Làm mới giọng")
                    with gr.Accordion("🎙️ Thu âm giọng trực tiếp (Microphone)", open=False):
                        gr.Markdown("Thu 3–10 giây giọng để lưu vào thư mục `voice/`.")
                        mic_rec_c5 = gr.Audio(sources=["microphone"], type="filepath", label="Ghi âm")
                        mic_name_c5 = gr.Textbox(label="Tên giọng", value="my_voice", lines=1)
                        mic_save_c5 = gr.Button("Lưu vào danh sách giọng")
                        mic_status_c5 = gr.Textbox(label="Trạng thái", interactive=False, lines=1)
                    video_consent = gr.Checkbox(
                        label="Đây là giọng tôi / tôi có quyền dùng",
                        value=False,
                    )
                    read_style = gr.Dropdown(
                        label="Phong cách đọc",
                        choices=list(READ_STYLES.keys()),
                        value=DEFAULT_STYLE,
                    )
                    style_hint = gr.Textbox(
                        label="Gợi ý",
                        value=READ_STYLES[DEFAULT_STYLE]["hint"],
                        interactive=False,
                    )
                    speed = gr.Slider(
                        0.80, 1.25, value=1.00, step=0.05, label="Tốc độ"
                    )
                    volume = gr.Slider(
                        0.50, 2.00, value=1.00, step=0.10, label="Âm lượng"
                    )
                    preview_snip = gr.Textbox(
                        label="Câu nghe thử",
                        value=PREVIEW_SAMPLE,
                        lines=2,
                    )
                    nghe_btn = gr.Button("Nghe thử")
                    dub_btn = gr.Button("Đọc + ghép giọng", variant="primary")
                with gr.Column(scale=3, min_width=320):
                    voice_preview = gr.Audio(label="Bản nghe thử", type="filepath")
                    voice_out = gr.Audio(label="voice_new.wav (cả clip)", type="filepath")

        with gr.Column(visible=False) as panel_export:
            gr.Markdown(
                "### Vị trí chữ + xuất mp4\n"
                "**Kéo ô chữ trên khung** (viền xanh). Kéo **tay cầm hai bên** để đổi độ dài. "
                "Chọn **font / màu / cỡ** bên trái — preview cập nhật ngay. "
                "Video **Mp4 cuối** phía dưới chỉ xem kết quả — không kéo được.",
                elem_classes=["panel-title"],
            )
            _font_choices = available_fonts()
            _font_default = (
                DEFAULT_FONT if DEFAULT_FONT in _font_choices else _font_choices[0]
            )
            with gr.Row(equal_height=True):
                with gr.Column(scale=2, min_width=240):
                    pos_preset = gr.Radio(
                        choices=list(PRESETS.keys()),
                        value="Dưới",
                        label="Nhảy nhanh",
                    )
                    sub_font = gr.Dropdown(
                        label="Font chữ",
                        choices=_font_choices,
                        value=_font_default,
                        info="Font gắn (EN) thiếu dấu Việt — dùng Arial/Helvetica khi sub tiếng Việt.",
                    )
                    sub_text_color = gr.ColorPicker(
                        label="Màu chữ",
                        value=DEFAULT_TEXT_COLOR,
                    )
                    sub_font_size = gr.Slider(
                        20,
                        120,
                        value=DEFAULT_FONT_SIZE,
                        step=2,
                        label="Cỡ chữ (px trên video)",
                    )
                    sub_bg = gr.Checkbox(label="Có nền chữ", value=True)
                    sub_bg_color = gr.ColorPicker(
                        label="Màu nền",
                        value="#000000",
                        visible=True,
                    )
                    sub_bg_opacity = gr.Slider(
                        40,
                        100,
                        value=95,
                        step=5,
                        label="Đậm nền (che chữ gốc)",
                    )
                    pos_label = gr.Textbox(
                        label="Vị trí / độ dài",
                        value="50% × 88% · rộng 70%",
                        interactive=False,
                    )
                    preview_sec = gr.Number(value=1.0, label="Giây preview")
                    frame_btn = gr.Button("Xem khung", variant="secondary")
                    export_btn = gr.Button("Xuất mp4", variant="primary")
                    pos_x = gr.Slider(
                        5, 95, value=50, step=1, visible=False, label="x"
                    )
                    pos_y = gr.Slider(
                        5, 95, value=88, step=1, visible=False, label="y"
                    )
                    box_w = gr.Slider(
                        30, 92, value=70, step=1, visible=False, label="w"
                    )
                    preview_state = gr.State(None)
                with gr.Column(scale=3, min_width=360):
                    preview_html = gr.HTML(
                        value=PLACEHOLDER_HTML,
                        elem_id="sub-preview",
                        apply_default_css=False,
                        css_template=SUB_STAGE_CSS,
                        js_on_load=SUB_DRAG_ONLOAD,
                    )
                    final_out = gr.Video(
                        label="Mp4 cuối (sau khi Xuất — không kéo)",
                        interactive=False,
                        height=220,
                    )

        with gr.Column(visible=False) as panel_tts:
            gr.Markdown("### Thử giọng (không cần video)", elem_classes=["panel-title"])
            with gr.Row(equal_height=True):
                with gr.Column(scale=2, min_width=260):
                    voice = gr.Dropdown(
                        label="Giọng",
                        choices=list_voice_choices(),
                        value=(
                            list_voice_choices()[0] if list_voice_choices() else None
                        ),
                        interactive=True,
                    )
                    refresh = gr.Button("Làm mới / tải giọng sẵn")
                    upload = gr.UploadButton(
                        "Thêm file giọng",
                        file_types=UPLOAD_TYPES,
                        file_count="multiple",
                        type="filepath",
                    )
                    with gr.Accordion("🎙️ Thu âm giọng trực tiếp (Microphone)", open=False):
                        gr.Markdown("Thu 3–10 giây giọng để lưu vào thư mục `voice/`.")
                        mic_rec_tts = gr.Audio(sources=["microphone"], type="filepath", label="Ghi âm")
                        mic_name_tts = gr.Textbox(label="Tên giọng", value="my_voice", lines=1)
                        mic_save_tts = gr.Button("Lưu vào danh sách giọng")
                        mic_status_tts = gr.Textbox(label="Trạng thái", interactive=False, lines=1)
                    text = gr.Textbox(
                        label="Đoạn cần đọc",
                        lines=6,
                        placeholder="Xin chào, đây là bản đọc local.",
                    )
                    consent = gr.Checkbox(
                        label="Đây là giọng tôi / tôi có quyền dùng",
                        value=False,
                    )
                    tts_style = gr.Dropdown(
                        label="Phong cách đọc",
                        choices=list(READ_STYLES.keys()),
                        value=DEFAULT_STYLE,
                    )
                    tts_style_hint = gr.Textbox(
                        label="Gợi ý",
                        value=READ_STYLES[DEFAULT_STYLE]["hint"],
                        interactive=False,
                    )
                    go = gr.Button("Đọc", variant="primary")
                with gr.Column(scale=3, min_width=320):
                    status = gr.Textbox(label="Trạng thái", interactive=False)
                    audio_out = gr.Audio(label="Kết quả", type="filepath")
                    clip_out = gr.Audio(
                        label="Đoạn 8s clone",
                        type="filepath",
                    )

        with gr.Column(visible=False) as panel_settings:
            gr.Markdown(
                "### API dịch\n"
                "Key **của bạn**. Lưu **cả Gemini và OpenAI**: máy đang chọn chạy trước; "
                "429/lỗi thì tự đổi model rồi máy kia — không phải bấm Dịch lại. "
                "STT + giọng vẫn local.",
                elem_classes=["panel-title"],
            )
            with gr.Row():
                with gr.Column(scale=2, min_width=280):
                    set_provider = gr.Radio(
                        choices=list(PROVIDERS),
                        value="Gemini",
                        label="Nhà cung cấp",
                    )
                    set_key = gr.Textbox(
                        label="Gemini API key",
                        type="password",
                        placeholder="AIza… hoặc sk-…",
                    )
                    set_model = gr.Dropdown(
                        label="Model",
                        choices=list(GEMINI_MODELS),
                        value=GEMINI_MODELS[0],
                        allow_custom_value=True,
                    )
                    with gr.Row():
                        set_refresh = gr.Button("Tải danh sách model")
                        set_save = gr.Button("Lưu", variant="primary")
                with gr.Column(scale=2, min_width=280):
                    set_status = gr.Textbox(
                        label="Đã lưu",
                        interactive=False,
                        lines=6,
                    )

    nav_outs = [
        panel_video,
        panel_sub,
        panel_translate,
        panel_voice,
        panel_export,
        panel_tts,
        panel_settings,
        nav_video,
        nav_sub,
        nav_translate,
        nav_voice,
        nav_export,
        nav_tts,
        nav_settings,
    ]
    nav_video.click(lambda: _switch_nav("video"), outputs=nav_outs)
    nav_sub.click(lambda: _switch_nav("sub"), outputs=nav_outs)
    nav_translate.click(lambda: _switch_nav("translate"), outputs=nav_outs)
    nav_voice.click(lambda: _switch_nav("voice"), outputs=nav_outs).then(
        run_autolock,
        inputs=[job_id_box, target_box, draft_srt],
        outputs=[video_status, preview_snip],
    )
    _style_inputs = [
        preview_state,
        pos_x,
        pos_y,
        sub_bg,
        sub_bg_color,
        box_w,
        sub_bg_opacity,
        sub_text_color,
        sub_font,
        sub_font_size,
    ]
    nav_export.click(lambda: _switch_nav("export"), outputs=nav_outs).then(
        run_preview,
        inputs=[
            job_id_box,
            pos_x,
            pos_y,
            preview_sec,
            sub_bg,
            sub_bg_color,
            box_w,
            sub_bg_opacity,
            sub_text_color,
            sub_font,
            sub_font_size,
        ],
        outputs=[preview_html, preview_state, video_status],
    )
    nav_tts.click(lambda: _switch_nav("tts"), outputs=nav_outs)
    nav_settings.click(lambda: _switch_nav("settings"), outputs=nav_outs)

    ingest.click(
        run_video_ingest,
        inputs=[video_in, job_id_box],
        outputs=[
            wav_out,
            video_out,
            job_id_box,
            srt_box,
            srt_view,
            target_box,
            voice_out,
            preview_html,
            final_out,
            video_status,
        ],
    )
    transcribe_btn.click(
        run_transcribe,
        inputs=[job_id_box, stt_model, stt_lang],
        outputs=[srt_box, srt_view, video_status],
    )
    lock_srt_btn.click(
        run_lock_orig_srt,
        inputs=[job_id_box, srt_box],
        outputs=[srt_box, srt_view, target_box, video_status],
    ).then(lambda t: t or "", inputs=[srt_box], outputs=[draft_srt])
    translate_btn.click(
        run_translate,
        inputs=[job_id_box, srt_box, target_lang],
        outputs=[target_box, video_status],
    ).then(lambda t: t or "", inputs=[target_box], outputs=[draft_srt])
    paste_btn.click(
        run_use_pasted,
        inputs=[job_id_box, target_box],
        outputs=[target_box, video_status],
    ).then(lambda t: t or "", inputs=[target_box], outputs=[draft_srt])
    trans_file.upload(
        run_load_trans_file,
        inputs=[job_id_box, trans_file],
        outputs=[target_box, video_status],
    ).then(lambda t: t or "", inputs=[target_box], outputs=[draft_srt])
    lock_final_btn.click(
        run_lock_final,
        inputs=[job_id_box, target_box, draft_srt],
        outputs=[target_box, video_status, preview_snip],
    )
    target_box.change(lambda t: t or "", inputs=[target_box], outputs=[draft_srt])
    target_box.blur(lambda t: t or "", inputs=[target_box], outputs=[draft_srt])
    video_voice_refresh.click(lambda: refresh_dropdown(), outputs=video_voice)
    mic_save_c5.click(
        save_recorded_voice,
        inputs=[mic_rec_c5, mic_name_c5],
        outputs=[video_voice, mic_status_c5],
    )
    read_style.change(
        apply_read_style,
        inputs=[read_style],
        outputs=[speed, volume, style_hint],
    )
    nghe_btn.click(
        run_voice_preview,
        inputs=[
            job_id_box,
            video_voice,
            video_consent,
            speed,
            volume,
            preview_snip,
            read_style,
        ],
        outputs=[voice_preview, video_status],
    )
    dub_btn.click(
        run_dub,
        inputs=[
            job_id_box,
            video_voice,
            video_consent,
            speed,
            volume,
            target_box,
            draft_srt,
            read_style,
        ],
        outputs=[voice_out, video_status],
    )
    pos_preset.change(
        apply_pos_preset,
        inputs=[
            pos_preset,
            preview_state,
            sub_bg,
            sub_bg_color,
            box_w,
            sub_bg_opacity,
            sub_text_color,
            sub_font,
            sub_font_size,
        ],
        outputs=[pos_x, pos_y, pos_label, preview_html],
    )
    sub_bg.change(
        lambda on, state, x, y, color, w, op, tc, fn, fs: (
            gr.update(visible=True),
            _restyle(state, x, y, on, color, w, op, tc, fn, fs),
        ),
        inputs=[
            sub_bg,
            preview_state,
            pos_x,
            pos_y,
            sub_bg_color,
            box_w,
            sub_bg_opacity,
            sub_text_color,
            sub_font,
            sub_font_size,
        ],
        outputs=[sub_bg_color, preview_html],
    )
    sub_bg_color.change(restyle_preview, inputs=_style_inputs, outputs=preview_html)
    sub_bg_opacity.change(restyle_preview, inputs=_style_inputs, outputs=preview_html)
    sub_text_color.change(restyle_preview, inputs=_style_inputs, outputs=preview_html)
    sub_font.change(restyle_preview, inputs=_style_inputs, outputs=preview_html)
    sub_font_size.change(restyle_preview, inputs=_style_inputs, outputs=preview_html)
    frame_btn.click(
        run_preview,
        inputs=[
            job_id_box,
            pos_x,
            pos_y,
            preview_sec,
            sub_bg,
            sub_bg_color,
            box_w,
            sub_bg_opacity,
            sub_text_color,
            sub_font,
            sub_font_size,
        ],
        outputs=[preview_html, preview_state, video_status],
    )
    preview_html.click(
        apply_drag,
        outputs=[pos_x, pos_y, box_w, pos_label],
    )
    export_btn.click(
        run_export,
        inputs=[
            job_id_box,
            pos_x,
            pos_y,
            sub_bg,
            sub_bg_color,
            box_w,
            sub_bg_opacity,
            sub_text_color,
            sub_font,
            sub_font_size,
        ],
        outputs=[final_out, video_status],
    )
    set_provider.change(
        on_provider_change,
        inputs=[set_provider],
        outputs=[set_model, set_key],
    )
    set_refresh.click(
        refresh_cloud_models,
        inputs=[set_provider, set_key],
        outputs=[set_model, set_status],
    )
    set_save.click(
        save_settings_form,
        inputs=[set_provider, set_key, set_model],
        outputs=[set_status, engine_line],
    )
    refresh.click(lambda: refresh_dropdown(), outputs=voice)
    upload.upload(add_voice_file, inputs=upload, outputs=[voice, status])
    mic_save_tts.click(
        save_recorded_voice,
        inputs=[mic_rec_tts, mic_name_tts],
        outputs=[voice, mic_status_tts],
    )
    tts_style.change(
        lambda name: style_defaults(name)[2],
        inputs=[tts_style],
        outputs=[tts_style_hint],
    )
    go.click(
        generate,
        inputs=[voice, text, consent, tts_style],
        outputs=[audio_out, clip_out, status],
    )
    srt_box.change(lambda t: t, inputs=srt_box, outputs=srt_view)

    demo.load(
        load_settings_form,
        outputs=[set_provider, set_key, set_model, set_status, engine_line],
    )


if __name__ == "__main__":
    _ensure_dirs()
    preload_whisper(DEFAULT_MODEL)
    print(f"voice/ → {VOICE_DIR}", flush=True)
    print(f"jobs/  → {JOBS_DIR}", flush=True)
    print(f"out/   → {OUT_DIR}", flush=True)
    print("Mở http://127.0.0.1:7860", flush=True)
    demo.queue().launch(
        server_name="127.0.0.1",
        server_port=7860,
        inbrowser=True,
        allowed_paths=[str(VOICE_DIR), str(OUT_DIR), str(JOBS_DIR)],
        theme=THEME,
        css=CSS,
    )
