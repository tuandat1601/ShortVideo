#!/usr/bin/env python3
"""Dịch từng cue, giữ timestamp. BYOK Gemini/OpenAI, Ollama, hoặc dán tay."""
from __future__ import annotations

import json
import re
import ssl
import threading
import time
import urllib.error
import urllib.request

from settings import (
    GEMINI_MODELS,
    OPENAI_MODELS,
    active_model,
    load_settings,
    provider_key,
)
from stt import parse_srt, segments_to_srt, srt_timestamp
from video_job import Job

OLLAMA_URL = "http://127.0.0.1:11434"
PREFERRED = (
    "qwen2.5",
    "qwen2",
    "llama3.2",
    "llama3.1",
    "llama3",
    "gemma3",
    "gemma2",
    "mistral",
    "phi",
)
TARGET_LANGS = ("vi", "en", "zh", "ja", "ko")
LANG_NAME = {
    "vi": "tiếng Việt",
    "en": "English",
    "zh": "中文",
    "ja": "日本語",
    "ko": "한국어",
}

def _ssl_context() -> ssl.SSLContext:
    try:
        import certifi

        return ssl.create_default_context(cafile=certifi.where())
    except Exception:
        return ssl.create_default_context()


_CTX = _ssl_context()


class RateLimitError(RuntimeError):
    def __init__(
        self, message: str, retry_after: float = 20.0, kind: str = "minute"
    ):
        super().__init__(message)
        self.retry_after = retry_after
        self.kind = kind


def _retry_after(headers, body: str) -> float:
    if headers is not None:
        raw = headers.get("Retry-After")
        if raw:
            try:
                return min(60.0, max(5.0, float(raw)))
            except ValueError:
                pass
    delay = 0.0
    try:
        payload = json.loads(body)
        err = payload.get("error") if isinstance(payload, dict) else None
        details = (err or {}).get("details") if isinstance(err, dict) else []
        for item in details or []:
            if not isinstance(item, dict):
                continue
            if "RetryInfo" in str(item.get("@type") or ""):
                m = re.match(
                    r"([\d.]+)\s*s", str(item.get("retryDelay") or ""), re.I
                )
                if m:
                    delay = float(m.group(1))
    except (json.JSONDecodeError, TypeError, ValueError):
        m = re.search(r'"retryDelay"\s*:\s*"(\d+(?:\.\d+)?)\s*s"', body)
        if m:
            delay = float(m.group(1))
    if delay < 1:
        delay = 20.0
    return min(60.0, delay)


def _quota_kind(body: str) -> str:
    if "PerDay" in body or "RequestsPerDay" in body:
        return "day"
    if "PerMinute" in body or "RequestsPerMinute" in body:
        return "minute"
    return "other"


def _http_json(
    url: str,
    *,
    method: str = "GET",
    headers: dict | None = None,
    body: dict | None = None,
    timeout: int = 60,
) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Content-Type", "application/json")
    for key, value in (headers or {}).items():
        req.add_header(key, value)
    try:
        with urllib.request.urlopen(req, timeout=timeout, context=_CTX) as resp:
            raw = resp.read().decode("utf-8") or "{}"
    except urllib.error.HTTPError as exc:
        err = exc.read().decode("utf-8", errors="replace")
        if exc.code == 429 or "RESOURCE_EXHAUSTED" in err:
            kind = _quota_kind(err)
            raise RateLimitError(
                "API hết hạn mức request (429).",
                retry_after=_retry_after(exc.headers, err),
                kind=kind,
            ) from exc
        raise RuntimeError(f"API {exc.code}: {err[-600:]}") from exc
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Không gọi được API: {exc}") from exc
    try:
        parsed = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise RuntimeError("API không trả JSON.") from exc
    if not isinstance(parsed, dict):
        raise RuntimeError("API trả dữ liệu lạ.")
    return parsed


def list_ollama_models() -> list[str]:
    try:
        with urllib.request.urlopen(f"{OLLAMA_URL}/api/tags", timeout=2) as resp:
            data = json.loads(resp.read().decode("utf-8") or "{}")
    except (urllib.error.URLError, TimeoutError, json.JSONDecodeError, OSError):
        return []
    names: list[str] = []
    for item in data.get("models") or []:
        name = str(item.get("name") or "").strip()
        if name:
            names.append(name)
    return names


def pick_ollama_model(selected: str | None = None) -> str:
    names = list_ollama_models()
    if not names:
        raise RuntimeError(
            "Không thấy Ollama (http://127.0.0.1:11434). "
            "Cài Ollama rồi `ollama pull qwen2.5`, hoặc dán SRT dịch vào ô bản dịch."
        )
    if selected and selected in names:
        return selected
    lower = {n.split(":")[0].lower(): n for n in names}
    for pref in PREFERRED:
        for stem, full in lower.items():
            if stem.startswith(pref):
                return full
    return names[0]


def _strip_fence(raw: str) -> str:
    text = (raw or "").strip()
    text = re.sub(r"^```(?:srt)?\s*", "", text, flags=re.I)
    text = re.sub(r"\s*```$", "", text)
    return text.strip()


def _strip_num(line: str) -> str:
    return re.sub(r"^\s*\d+[\.\)\:、\-]\s*", "", line).strip()


_TS_LINE = re.compile(
    r"\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}\s*-->\s*\d{1,2}:\d{2}:\d{2}[,.]\d{1,3}"
)


def parse_translated_lines(raw: str, expected: int) -> list[str]:
    cleaned = _strip_fence(raw)
    try:
        rows = parse_srt(cleaned, strict=False)
        texts = [(t or "").strip() for _s, _e, t in rows]
        texts = [t for t in texts if t]
        if len(texts) == expected:
            return texts
        if len(texts) > expected:
            return texts[:expected]
    except RuntimeError:
        pass
    lines = []
    for ln in cleaned.splitlines():
        s = ln.strip()
        if not s or s.isdigit() or _TS_LINE.search(s):
            continue
        lines.append(_strip_num(s))
    lines = [ln for ln in lines if ln]
    skip = (
        "here",
        "sure",
        "ok",
        "đây",
        "bản dịch",
        "translation",
        "sure,",
        "here is",
        "webvtt",
        "```",
    )
    while lines and any(lines[0].lower().startswith(s) for s in skip) and len(lines) > expected:
        lines = lines[1:]
    if len(lines) == expected:
        return lines
    if len(lines) > expected:
        return lines[:expected]
    raise RuntimeError(
        f"Bản dịch {len(lines)} câu, gốc {expected} câu. "
        "Sửa tay cho khớp số câu, hoặc dán SRT dịch vào ô."
    )


def _plain_cue_lines(raw: str) -> list[str]:
    lines: list[str] = []
    for ln in _strip_fence(raw).splitlines():
        s = ln.strip()
        if not s or s.isdigit() or _TS_LINE.search(s):
            continue
        low = s.lower()
        if low in {"webvtt", "note"} or low.startswith("note "):
            continue
        if s.startswith("```"):
            continue
        lines.append(_strip_num(s))
    return [ln for ln in lines if ln]


def _fit_count(
    texts: list[str], orig: list[tuple[float, float, str]]
) -> list[str]:
    n = len(orig)
    cleaned = [(t or "").strip() for t in texts if (t or "").strip()]
    if len(cleaned) > n:
        return cleaned[:n]
    if len(cleaned) < n:
        return cleaned + [t for _s, _e, t in orig[len(cleaned) :]]
    return cleaned


def apply_texts(
    orig_rows: list[tuple[float, float, str]], texts: list[str]
) -> str:
    if len(texts) != len(orig_rows):
        raise RuntimeError(
            f"Số câu dịch ({len(texts)}) khác số câu gốc ({len(orig_rows)})."
        )
    rows = [
        (start, end, (text or "").strip() or orig)
        for (start, end, orig), text in zip(orig_rows, texts)
    ]
    return segments_to_srt(rows)


def apply_pasted_srt(orig_raw: str, pasted: str) -> str:
    orig = parse_srt(orig_raw)
    blob = (pasted or "").strip()
    if not blob:
        return segments_to_srt(orig)

    srt_texts: list[str] = []
    try:
        srt_texts = [
            (t or "").strip()
            for _s, _e, t in parse_srt(blob, strict=False)
        ]
        srt_texts = [t for t in srt_texts if t]
    except RuntimeError:
        srt_texts = []

    if len(srt_texts) == len(orig):
        texts = srt_texts
    elif srt_texts:
        texts = _fit_count(srt_texts, orig)
    else:
        try:
            texts = parse_translated_lines(blob, len(orig))
        except RuntimeError:
            texts = _fit_count(_plain_cue_lines(blob), orig)
    return apply_texts(orig, texts)


def _ollama_generate(model: str, prompt: str) -> str:
    data = _http_json(
        f"{OLLAMA_URL}/api/generate",
        method="POST",
        body={
            "model": model,
            "prompt": prompt,
            "stream": False,
            "options": {"temperature": 0.2},
        },
        timeout=180,
    )
    text = (data.get("response") or "").strip()
    if not text:
        raise RuntimeError("Ollama trả về trống.")
    return text


_gemini_lock = threading.Lock()
_gemini_next = 0.0
_gemini_gap = 0.0


def _note_gemini_rate_limit() -> None:
    global _gemini_gap
    _gemini_gap = 13.0


def _gemini_slot() -> None:
    global _gemini_next
    with _gemini_lock:
        wait = _gemini_next - time.monotonic()
        if wait > 0:
            time.sleep(wait)
        _gemini_next = time.monotonic() + _gemini_gap


def _gemini_generate(model: str, key: str, prompt: str) -> str:
    _gemini_slot()
    url = (
        "https://generativelanguage.googleapis.com/v1beta/models/"
        f"{model}:generateContent?key={key}"
    )
    try:
        data = _http_json(
            url,
            method="POST",
            body={
                "contents": [{"parts": [{"text": prompt}]}],
                "generationConfig": {
                    "temperature": 0.2,
                    "maxOutputTokens": 16384,
                },
            },
            timeout=180,
        )
    except RateLimitError:
        _note_gemini_rate_limit()
        raise
    cands = data.get("candidates") or []
    if not cands:
        raise RuntimeError("Gemini không trả candidate (chặn/an toàn?).")
    parts = ((cands[0].get("content") or {}).get("parts")) or []
    text = "".join(str(p.get("text") or "") for p in parts).strip()
    if not text:
        raise RuntimeError("Gemini trả về trống.")
    return text


def _openai_generate(model: str, key: str, prompt: str) -> str:
    data = _http_json(
        "https://api.openai.com/v1/chat/completions",
        method="POST",
        headers={"Authorization": f"Bearer {key}"},
        body={
            "model": model,
            "temperature": 0.2,
            "max_tokens": 16384,
            "messages": [
                {
                    "role": "system",
                    "content": PROMPT_RULES + " Output SRT only.",
                },
                {"role": "user", "content": prompt},
            ],
        },
        timeout=180,
    )
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError("OpenAI không trả choice.")
    text = str((choices[0].get("message") or {}).get("content") or "").strip()
    if not text:
        raise RuntimeError("OpenAI trả về trống.")
    return text


def list_gemini_models(key: str) -> list[str]:
    if not (key or "").strip():
        return list(GEMINI_MODELS)
    try:
        data = _http_json(
            f"https://generativelanguage.googleapis.com/v1beta/models?key={key.strip()}",
            timeout=20,
        )
    except RuntimeError:
        return list(GEMINI_MODELS)
    names: list[str] = []
    for item in data.get("models") or []:
        methods = item.get("supportedGenerationMethods") or []
        if "generateContent" not in methods:
            continue
        name = str(item.get("name") or "").split("/")[-1]
        if name.startswith("gemini"):
            names.append(name)
    return names or list(GEMINI_MODELS)


def list_openai_models(key: str) -> list[str]:
    if not (key or "").strip():
        return list(OPENAI_MODELS)
    try:
        data = _http_json(
            "https://api.openai.com/v1/models",
            headers={"Authorization": f"Bearer {key.strip()}"},
            timeout=20,
        )
    except RuntimeError:
        return list(OPENAI_MODELS)
    names: list[str] = []
    for item in data.get("data") or []:
        mid = str(item.get("id") or "")
        if mid.startswith(("gpt-4", "gpt-5", "o4", "o3")):
            names.append(mid)
    names = sorted(set(names))
    return names or list(OPENAI_MODELS)


BATCH_MIN = 50
BATCH = 80
BATCH_MAX = 100
CHUNK_OLLAMA = 50
CLOUD_WORKERS = 3
RATE_LIMIT_TRIES = 6
GEMINI_FALLBACK = ("gemini-2.5-flash", "gemini-2.0-flash")
OPENAI_FALLBACK = ("gpt-4o-mini",)
PROMPT_RULES = (
    "Chỉ dịch nội dung thoại, giữ nguyên timestamp và số thứ tự, không giải thích thêm."
)


def _rate_limit_message(provider: str, model: str, kind: str) -> str:
    if provider == "Gemini" and kind == "day":
        return (
            f"Gemini hết hạn mức ngày (free) cho {model}. "
            "Đợi reset, chọn model khác, hoặc thêm OpenAI key ở Cài đặt (tự đổi máy khi lỗi)."
        )
    if provider == "Gemini":
        return (
            f"Gemini free tier ~5 request/phút cho {model}. "
            "Thêm OpenAI key ở Cài đặt để tự đổi máy, hoặc đợi ~1 phút rồi Dịch lại."
        )
    return (
        f"{provider} hết hạn mức request (429). "
        "Đợi rồi bấm Dịch lại, hoặc lưu thêm key máy kia ở Cài đặt."
    )


def _cue_block(rows: list) -> str:
    parts: list[str] = []
    for i, (start, end, text) in enumerate(rows, 1):
        parts.append(str(i))
        parts.append(f"{srt_timestamp(start)} --> {srt_timestamp(end)}")
        parts.append((text or "").strip())
        parts.append("")
    return "\n".join(parts).strip()


def _chunk_prompt(rows: list, target_lang: str) -> str:
    lang = (target_lang or "vi").strip().lower()
    if lang not in TARGET_LANGS:
        lang = "vi"
    dest = LANG_NAME[lang]
    return (
        f"{PROMPT_RULES}\n"
        f"Dịch thoại sang {dest}. Trả về đúng {len(rows)} cue SRT "
        f"(số thứ tự + timestamp + câu dịch). "
        f"Không gộp, không tách, không dịch mốc giờ, không markdown, không lời dẫn.\n\n"
        f"{_cue_block(rows)}"
    )


def _generate(provider: str, model: str, key: str, prompt: str) -> str:
    if provider == "Ollama":
        return _ollama_generate(model, prompt)
    if provider == "OpenAI":
        return _openai_generate(model, key, prompt)
    return _gemini_generate(model, key, prompt)


def _can_failover(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError):
        return True
    msg = str(exc).lower()
    return any(
        n in msg
        for n in (
            "401",
            "403",
            "429",
            "404",
            "500",
            "502",
            "503",
            "resource_exhausted",
            "hết hạn mức",
            "không gọi được",
            "timed out",
            "timeout",
            "trả về trống",
            "candidate",
            "chặn",
            "câu, gốc",
            "bản dịch ",
            "invalid",
            "api key",
        )
    )


def _skip_provider(exc: Exception) -> bool:
    if isinstance(exc, RateLimitError) and exc.kind == "day":
        return True
    msg = str(exc).lower()
    return any(
        n in msg
        for n in (
            "401",
            "403",
            "invalid api",
            "api key not valid",
            "incorrect api key",
            "invalid_api_key",
        )
    )


def _push_engine(
    chain: list[tuple[str, str, str]],
    seen: set[tuple[str, str]],
    provider: str,
    model: str,
    key: str,
) -> None:
    model = (model or "").strip()
    if not model:
        return
    if provider != "Ollama" and not (key or "").strip():
        return
    tag = (provider, model)
    if tag in seen:
        return
    seen.add(tag)
    chain.append((provider, model, (key or "").strip()))


def _engine_chain(cfg: dict) -> list[tuple[str, str, str]]:
    primary = cfg.get("provider") or "Gemini"
    chain: list[tuple[str, str, str]] = []
    seen: set[tuple[str, str]] = set()
    g_key = provider_key(cfg, "Gemini")
    o_key = provider_key(cfg, "OpenAI")
    g_model = (cfg.get("gemini_model") or GEMINI_MODELS[0]).strip()
    o_model = (cfg.get("openai_model") or OPENAI_MODELS[0]).strip()

    if primary == "Ollama":
        try:
            _push_engine(chain, seen, "Ollama", pick_ollama_model(active_model(cfg)), "")
        except RuntimeError:
            pass
    elif primary == "OpenAI":
        _push_engine(chain, seen, "OpenAI", o_model, o_key)
    else:
        _push_engine(chain, seen, "Gemini", g_model, g_key)

    if g_key:
        _push_engine(chain, seen, "Gemini", g_model, g_key)
        if not o_key:
            for name in GEMINI_FALLBACK:
                _push_engine(chain, seen, "Gemini", name, g_key)
    if o_key:
        _push_engine(chain, seen, "OpenAI", o_model, o_key)
        for name in OPENAI_FALLBACK:
            _push_engine(chain, seen, "OpenAI", name, o_key)

    if primary != "Ollama":
        try:
            _push_engine(chain, seen, "Ollama", pick_ollama_model(), "")
        except RuntimeError:
            pass
    return chain


def _translate_chunk(
    rows: list,
    target_lang: str,
    provider: str,
    model: str,
    key: str,
    *,
    failover: bool = False,
) -> list[str]:
    prompt = _chunk_prompt(rows, target_lang)
    last_err: Exception | None = None
    tries = 1 if failover else RATE_LIMIT_TRIES
    for attempt in range(tries):
        try:
            raw = _generate(provider, model, key, prompt)
            return parse_translated_lines(raw, len(rows))
        except RateLimitError as exc:
            last_err = exc
            if exc.kind == "day" or failover:
                break
            time.sleep(min(60.0, exc.retry_after * (1.15**attempt)))
        except RuntimeError as exc:
            last_err = exc
            if failover or "câu" in str(exc) or attempt >= 1:
                break
    if isinstance(last_err, RateLimitError):
        if failover:
            raise last_err
        raise RuntimeError(
            _rate_limit_message(provider, model, last_err.kind)
        ) from last_err
    raise RuntimeError(str(last_err) if last_err else "Dịch lô thất bại.")


def _make_chunks(rows: list, provider: str) -> list:
    n = len(rows)
    if n <= BATCH_MAX:
        return [rows]
    size = CHUNK_OLLAMA if provider == "Ollama" else BATCH
    return [rows[i : i + size] for i in range(0, n, size)]


def _run_chunks_parallel(
    chunks: list,
    target_lang: str,
    provider: str,
    model: str,
    key: str,
) -> list[str]:
    from concurrent.futures import ThreadPoolExecutor, as_completed

    bag: list[list[str] | None] = [None] * len(chunks)
    workers = min(CLOUD_WORKERS, len(chunks))
    with ThreadPoolExecutor(max_workers=workers) as pool:
        futs = {
            pool.submit(
                _translate_chunk, chunk, target_lang, provider, model, key
            ): i
            for i, chunk in enumerate(chunks)
        }
        for fut in as_completed(futs):
            bag[futs[fut]] = fut.result()
    texts: list[str] = []
    for part in bag:
        if not part:
            raise RuntimeError("Một lô dịch trả về trống.")
        texts.extend(part)
    return texts


def _run_chunks_failover(
    chunks: list, target_lang: str, chain: list[tuple[str, str, str]]
) -> tuple[list[str], str]:
    texts: list[str] = []
    used: list[str] = []
    engine_i = 0
    skipped: set[str] = set()
    last_err: Exception | None = None

    def usable(start: int) -> int:
        j = start
        while j < len(chain) and chain[j][0] in skipped:
            j += 1
        return j

    for chunk in chunks:
        engine_i = usable(engine_i)
        ok = False
        while engine_i < len(chain):
            provider, model, key = chain[engine_i]
            more = any(
                chain[k][0] not in skipped for k in range(engine_i + 1, len(chain))
            )
            try:
                texts.extend(
                    _translate_chunk(
                        chunk,
                        target_lang,
                        provider,
                        model,
                        key,
                        failover=more,
                    )
                )
                tag = f"{provider}/{model}"
                if not used or used[-1] != tag:
                    used.append(tag)
                last_err = None
                ok = True
                break
            except Exception as exc:
                last_err = exc
                if not more or not _can_failover(exc):
                    if isinstance(exc, RateLimitError):
                        raise RuntimeError(
                            _rate_limit_message(provider, model, exc.kind)
                        ) from exc
                    raise
                if _skip_provider(exc):
                    skipped.add(provider)
                    engine_i = usable(engine_i + 1)
                else:
                    engine_i = usable(engine_i + 1)
        if not ok:
            if isinstance(last_err, RateLimitError):
                p, m, _k = chain[min(engine_i, len(chain) - 1)]
                raise RuntimeError(_rate_limit_message(p, m, last_err.kind)) from last_err
            raise RuntimeError(str(last_err) if last_err else "Dịch thất bại.")
    return texts, " → ".join(used)


def translate_cues(orig_raw: str, target_lang: str) -> tuple[str, str]:
    orig = parse_srt(orig_raw)
    cfg = load_settings()
    chain = _engine_chain(cfg)
    if not chain:
        raise RuntimeError(
            "Chưa có máy dịch. Lưu Gemini hoặc OpenAI key ở Cài đặt, "
            "hoặc bật Ollama, hoặc dán SRT vào ô bản dịch."
        )

    chunks = _make_chunks(orig, chain[0][0])
    provider, model, key = chain[0]
    extra = f" · {len(chunks)} lô" if len(chunks) > 1 else ""

    def _run(parts: list) -> tuple[list[str], str]:
        p0, m0, k0 = chain[0]
        if p0 == "OpenAI" and len(parts) > 1:
            try:
                return _run_chunks_parallel(parts, target_lang, p0, m0, k0), f"OpenAI/{m0}"
            except Exception:
                if len(chain) == 1:
                    raise
                return _run_chunks_failover(parts, target_lang, chain)
        if len(chain) == 1:
            out: list[str] = []
            for chunk in parts:
                out.extend(_translate_chunk(chunk, target_lang, p0, m0, k0))
            return out, f"{p0}/{m0}"
        return _run_chunks_failover(parts, target_lang, chain)

    try:
        texts, used = _run(chunks)
    except RuntimeError as exc:
        # Một phát quá dài → cắt nhỏ như chat bị trunc, gọi lại.
        small = BATCH_MIN
        if "câu" in str(exc) and len(chunks) == 1 and len(orig) > small:
            chunks = [orig[i : i + small] for i in range(0, len(orig), small)]
            extra = f" · {len(chunks)} lô"
            texts, used = _run(chunks)
        else:
            raise

    srt = apply_texts(orig, texts)
    return srt, used + extra


def save_target_srt(job: Job, raw: str) -> tuple[str, str]:
    if not job.orig_srt.exists():
        raise RuntimeError("Chưa khóa orig.srt. Cửa 2 trước.")
    orig = job.orig_srt.read_text(encoding="utf-8")
    srt = apply_pasted_srt(orig, raw)
    job.target_srt.write_text(srt, encoding="utf-8")
    n = len(parse_srt(srt))
    return srt, f"Đã lưu {job.target_srt.name} · {n} câu. Chưa TTS."


def lock_final_srt(job: Job, raw: str) -> tuple[str, str]:
    srt, _ = save_target_srt(job, raw)
    job.final_srt.write_text(srt, encoding="utf-8")
    n = len(parse_srt(srt))
    return srt, f"Đã khóa {job.final_srt.name} · {n} câu. Sang cửa 4 (giọng)."


def ensure_final_srt(job: Job, raw: str = "") -> tuple[str, str]:
    """Ghi final.srt từ ô dán, rồi target/final/orig trên đĩa — không bắt cửa 3 nếu đã khóa sub."""
    pasted = (raw or "").strip()
    if pasted:
        return lock_final_srt(job, pasted)
    if job.final_srt.exists() and job.final_srt.read_text(encoding="utf-8").strip():
        srt = job.final_srt.read_text(encoding="utf-8")
        n = len(parse_srt(srt))
        return srt, f"Đã có {job.final_srt.name} · {n} câu."
    if job.target_srt.exists() and job.target_srt.read_text(encoding="utf-8").strip():
        return lock_final_srt(
            job, job.target_srt.read_text(encoding="utf-8")
        )
    if job.orig_srt.exists() and job.orig_srt.read_text(encoding="utf-8").strip():
        srt, note = lock_final_srt(
            job, job.orig_srt.read_text(encoding="utf-8")
        )
        return srt, note + " (đọc bản gốc — chưa dán dịch)."
    raise RuntimeError("Chưa khóa orig.srt. Cửa 2: Dùng bản sub này.")
