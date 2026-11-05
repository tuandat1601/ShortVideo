#!/usr/bin/env python3
"""Cài đặt BYOK dịch: Gemini / OpenAI / Ollama. File local, không commit."""
from __future__ import annotations

import json
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SETTINGS_PATH = ROOT / "settings.json"

PROVIDERS = ("Gemini", "OpenAI", "Ollama")
GEMINI_MODELS = (
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "gemini-2.0-flash",
    "gemini-1.5-flash",
    "gemini-1.5-pro",
)
OPENAI_MODELS = (
    "gpt-4o-mini",
    "gpt-4o",
    "gpt-4.1-mini",
    "gpt-4.1",
    "o4-mini",
)

_EMPTY = {
    "provider": "Gemini",
    "gemini_key": "",
    "openai_key": "",
    "gemini_model": GEMINI_MODELS[0],
    "openai_model": OPENAI_MODELS[0],
    "ollama_model": "",
}


def load_settings() -> dict:
    data = dict(_EMPTY)
    if SETTINGS_PATH.exists():
        try:
            raw = json.loads(SETTINGS_PATH.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                data.update({k: raw[k] for k in _EMPTY if k in raw})
        except (json.JSONDecodeError, OSError):
            pass
    if not data.get("gemini_key"):
        data["gemini_key"] = (
            os.environ.get("GEMINI_API_KEY") or os.environ.get("GOOGLE_API_KEY") or ""
        )
    if not data.get("openai_key"):
        data["openai_key"] = os.environ.get("OPENAI_API_KEY") or ""
    provider = data.get("provider") or "Gemini"
    if provider not in PROVIDERS:
        provider = "Gemini"
    data["provider"] = provider
    return data


def save_settings(provider: str, key: str, model: str) -> dict:
    data = load_settings()
    provider = provider if provider in PROVIDERS else "Gemini"
    data["provider"] = provider
    key = (key or "").strip()
    model = (model or "").strip()
    if provider == "Gemini":
        if key:
            data["gemini_key"] = key
        if model:
            data["gemini_model"] = model
    elif provider == "OpenAI":
        if key:
            data["openai_key"] = key
        if model:
            data["openai_model"] = model
    else:
        if model:
            data["ollama_model"] = model
    SETTINGS_PATH.write_text(
        json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    return data


def mask_key(key: str) -> str:
    text = (key or "").strip()
    if not text:
        return "(chưa có)"
    if len(text) <= 8:
        return "••••"
    return f"…{text[-4:]}"


def active_key(data: dict | None = None) -> str:
    data = data or load_settings()
    return provider_key(data, data.get("provider") or "Gemini")


def provider_key(data: dict | None, provider: str) -> str:
    data = data or load_settings()
    if provider == "OpenAI":
        return (data.get("openai_key") or "").strip()
    if provider == "Gemini":
        return (data.get("gemini_key") or "").strip()
    return ""


def active_model(data: dict | None = None) -> str:
    data = data or load_settings()
    provider = data.get("provider") or "Gemini"
    if provider == "OpenAI":
        return data.get("openai_model") or OPENAI_MODELS[0]
    if provider == "Ollama":
        return data.get("ollama_model") or ""
    return data.get("gemini_model") or GEMINI_MODELS[0]


def settings_summary(data: dict | None = None) -> str:
    data = data or load_settings()
    provider = data.get("provider") or "Gemini"
    model = active_model(data) or "(chưa chọn model)"
    if provider == "Ollama":
        spare = []
        if (data.get("gemini_key") or "").strip():
            spare.append("Gemini")
        if (data.get("openai_key") or "").strip():
            spare.append("OpenAI")
        extra = f" · lỗi → {'/'.join(spare)}" if spare else ""
        return f"Ollama · {model or '(chưa có model)'} — không cần key.{extra}"
    key = active_key(data)
    spare = []
    if provider != "Gemini" and (data.get("gemini_key") or "").strip():
        spare.append("Gemini")
    if provider != "OpenAI" and (data.get("openai_key") or "").strip():
        spare.append("OpenAI")
    extra = f" · lỗi → {'/'.join(spare)}" if spare else ""
    return f"{provider} · {model} · key {mask_key(key)}{extra}"
