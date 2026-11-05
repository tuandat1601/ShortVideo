#!/usr/bin/env python3
"""Module TTS tiếng Anh biểu cảm (Kokoro ONNX) chạy 100% Local trên máy."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import soundfile as sf

ROOT = Path(__file__).resolve().parent
MODELS_DIR = ROOT / "models" / "kokoro"
MODEL_PATH = MODELS_DIR / "kokoro-v1.0.onnx"
VOICES_PATH = MODELS_DIR / "voices-v1.0.bin"

KOKORO_PRESET_PREFIX = "【EN】"

# Giọng tuyển chọn với mô tả tiếng Việt thân thiện
CURATED_VOICES: dict[str, str] = {
    "【EN Devlog / Trầm ấm】am_adam": "am_adam",
    "【EN Devlog Trẻ / Độc quyền】blend_young_devlog": "blend:am_adam:0.65:am_puck:0.35",
    "【EN Podcast / Tự sự】am_michael": "am_michael",
    "【EN Deep Calm / Điềm tĩnh】am_echo": "am_echo",
    "【EN British Story / Kể chuyện】bm_george": "bm_george",
    "【EN British Chill / Thư thái】bm_lewis": "bm_lewis",
    "【EN Trẻ trung / Hóm hỉnh】am_puck": "am_puck",
    "【EN Nữ ấm áp / Truyền cảm】af_heart": "af_heart",
    "【EN Nữ tự nhiên / Rõ ràng】af_bella": "af_bella",
    "【EN Nữ nhẹ nhàng / Dịu êm】af_nicole": "af_nicole",
    "【EN Nữ kể chuyện / Tự sự】af_sarah": "af_sarah",
}

_kokoro_instance = None


def is_available() -> bool:
    try:
        import kokoro_onnx  # noqa: F401
        return MODEL_PATH.exists() and VOICES_PATH.exists()
    except Exception:
        return False


def get_kokoro_engine():
    global _kokoro_instance
    if _kokoro_instance is not None:
        return _kokoro_instance
    from kokoro_onnx import Kokoro

    if not MODEL_PATH.exists() or not VOICES_PATH.exists():
        raise RuntimeError(
            f"Chưa thấy model Kokoro tại {MODELS_DIR}.\n"
            "Cần kokoro-v1.0.onnx và voices-v1.0.bin."
        )
    _kokoro_instance = Kokoro(str(MODEL_PATH), str(VOICES_PATH))
    return _kokoro_instance


def list_english_voice_choices() -> list[str]:
    """Trả về danh sách giọng tiếng Anh có nhãn rõ ràng."""
    return list(CURATED_VOICES.keys())


def resolve_voice_id(label: str) -> str:
    """Chuyển nhãn UI về voice_id của Kokoro."""
    if label in CURATED_VOICES:
        return CURATED_VOICES[label]
    # Nếu truyền thẳng voice_id (vd: am_adam)
    raw = label.strip()
    if raw.startswith(KOKORO_PRESET_PREFIX):
        raw = raw[len(KOKORO_PRESET_PREFIX):].strip()
    return raw


def synthesize_english(
    text: str,
    voice_label: str,
    dest_path: Path,
    speed: float = 1.0,
) -> tuple[Path, float]:
    """Đọc câu text tiếng Anh sang file WAV (24kHz)."""
    cleaned = (text or "").strip()
    if not cleaned:
        raise RuntimeError("Câu trống, không thể đọc.")

    engine = get_kokoro_engine()
    voice_id = resolve_voice_id(voice_label)

    if isinstance(voice_id, str) and voice_id.startswith("blend:"):
        parts = voice_id.split(":")
        s1 = engine.get_voice_style(parts[1])
        w1 = float(parts[2])
        s2 = engine.get_voice_style(parts[3])
        w2 = float(parts[4])
        voice_target = (w1 * s1) + (w2 * s2)
        lang = "en-us"
    else:
        voice_target = voice_id
        lang = "en-gb" if str(voice_id).startswith("b") else "en-us"

    dest_path.parent.mkdir(parents=True, exist_ok=True)
    samples, sample_rate = engine.create(
        cleaned,
        voice=voice_target,
        speed=float(speed),
        lang=lang,
    )
    sf.write(str(dest_path), samples, sample_rate)
    duration = float(len(samples)) / float(sample_rate)
    return dest_path, duration
