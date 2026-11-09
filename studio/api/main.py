"""FastAPI: lớp mỏng bọc core. Chạy:  uvicorn studio.api.main:app --port 8000"""
from __future__ import annotations

import shutil
import time
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, UploadFile
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from ..core.project import PROJECTS_DIR, Project, list_projects

app = FastAPI(title="Shorts Studio")
app.add_middleware(
    CORSMiddleware, allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["*"], allow_headers=["*"],
)
PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
app.mount("/files", StaticFiles(directory=str(PROJECTS_DIR)), name="files")


def _load(pid: str) -> Project:
    try:
        return Project.load(pid)
    except FileNotFoundError as e:
        raise HTTPException(404, str(e))


@app.get("/api/projects")
def projects():
    return list_projects()


@app.post("/api/projects")
def create_project(body: dict | None = None):
    return Project.create((body or {}).get("name", "Untitled"))


@app.get("/api/projects/{pid}")
def get_project(pid: str):
    return _load(pid)


@app.put("/api/projects/{pid}")
def put_project(pid: str, proj: Project):
    if proj.id != pid:
        raise HTTPException(400, "id không khớp")
    proj.save()
    return proj


@app.post("/api/projects/{pid}/voice")
async def make_voice(pid: str, body: dict | None = None):
    from ..core.workflows.voiceover import build_voiceover

    proj = _load(pid)
    seg_id = (body or {}).get("segment_id")
    try:
        return await run_in_threadpool(build_voiceover, proj, seg_id)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/{pid}/assemble-voice")
async def assemble_voice_endpoint(pid: str):
    from ..core.workflows.voiceover import assemble_master_voice

    proj = _load(pid)
    try:
        return await run_in_threadpool(assemble_master_voice, proj)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/{pid}/auto-broll")
def make_auto_broll(pid: str):
    from ..core.workflows.voiceover import auto_broll

    proj = _load(pid)
    try:
        return auto_broll(proj)
    except Exception as e:
        raise HTTPException(400, str(e))


@app.post("/api/projects/{pid}/render")
async def render(pid: str, body: dict | None = None):
    from ..render.compiler import render_project

    proj = _load(pid)
    export_dir = (body or {}).get("export_dir") or proj.export_dir
    quality = (body or {}).get("quality", "1080p")
    eco_mode = bool((body or {}).get("eco_mode", True))

    target_out = None
    if export_dir and export_dir != "project":
        exp_path = Path(export_dir).expanduser().resolve()
        exp_path.mkdir(parents=True, exist_ok=True)
        filename = f"{proj.name or proj.id}_{quality}.mp4".replace(" ", "_")
        target_out = exp_path / filename

    try:
        out = await run_in_threadpool(render_project, proj, target_out, quality, eco_mode)
    except Exception as e:
        raise HTTPException(400, str(e))

    default_name = f"{proj.name or proj.id}_{quality}.mp4".replace(" ", "_")
    return {
        "url": f"/files/{pid}/out/{default_name}",
        "saved_path": str(out),
        "filename": Path(out).name,
    }


@app.post("/api/projects/{pid}/crop-source")
async def crop_source(pid: str, body: dict):
    from ..render.compiler import crop_clip_source

    proj = _load(pid)
    src = body.get("src")
    if not src:
        raise HTTPException(400, "Thiếu src của file")
    crop_x = float(body.get("crop_x", 50.0))
    crop_y = float(body.get("crop_y", 50.0))
    crop_scale = float(body.get("crop_scale", 100.0))
    name = body.get("name")

    try:
        new_src = await run_in_threadpool(
            crop_clip_source,
            proj,
            src,
            crop_x,
            crop_y,
            crop_scale,
            name,
        )
    except Exception as e:
        raise HTTPException(400, f"Lỗi cắt video nguồn: {e}")

    return {"src": new_src, "url": f"/files/{pid}/{new_src}"}


@app.post("/api/reveal-file")
def reveal_file(body: dict):
    path_str = body.get("path")
    if not path_str:
        raise HTTPException(400, "Thiếu đường dẫn file")
    p = Path(path_str).expanduser().resolve()
    if not p.exists():
        raise HTTPException(404, f"Không tìm thấy file: {p}")
    import subprocess
    import sys

    if sys.platform == "darwin":
        subprocess.run(["open", "-R", str(p)])
    elif sys.platform.startswith("win"):
        subprocess.run(["explorer", f"/select,{str(p)}"])
    else:
        subprocess.run(["xdg-open", str(p.parent)])
    return {"status": "ok"}


@app.post("/api/projects/{pid}/media")
async def upload_media(pid: str, file: UploadFile):
    proj = _load(pid)
    proj.media_dir.mkdir(parents=True, exist_ok=True)
    name = Path(file.filename or "upload").name
    dest = proj.media_dir / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    return {"src": f"media/{name}"}


@app.get("/api/media/{pid}")
def list_media(pid: str):
    proj = _load(pid)
    if not proj.media_dir.exists():
        return []
    return [f"media/{p.name}" for p in sorted(proj.media_dir.iterdir()) if p.is_file()]


@app.get("/api/stickers")
def list_stickers():
    p = Path(__file__).resolve().parents[1] / "assets" / "stickers"
    if not p.exists():
        return []
    return [f.name for f in sorted(p.glob("*.png"))]


@app.post("/api/projects/{pid}/add-sticker/{name}")
def add_sticker_to_project(pid: str, name: str):
    proj = _load(pid)
    src_sticker = Path(__file__).resolve().parents[1] / "assets" / "stickers" / name
    if not src_sticker.exists():
        raise HTTPException(404, "Không thấy sticker này")
    proj.media_dir.mkdir(parents=True, exist_ok=True)
    dest = proj.media_dir / name
    shutil.copy2(src_sticker, dest)
    return {"src": f"media/{name}"}


@app.post("/api/projects/{pid}/bgm")
async def upload_bgm(pid: str, file: UploadFile):
    proj = _load(pid)
    proj.media_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(file.filename or "bgm.mp3").suffix or ".mp3"
    name = f"bgm_{int(time.time())}{ext}"
    dest = proj.media_dir / name
    with dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)
    proj.bgm_file = f"media/{name}"
    proj.save()
    return proj


@app.delete("/api/projects/{pid}/bgm")
def delete_bgm(pid: str):
    proj = _load(pid)
    proj.bgm_file = None
    proj.save()
    return proj


@app.post("/api/preview-voice")
async def preview_voice(body: dict):
    from ..engines import tts_kokoro, tts_vieneu  # noqa: F401
    from ..engines.base import get_tts

    voice = body.get("voice", "")
    if not voice:
        raise HTTPException(400, "Thiếu tên giọng")
    speed = float(body.get("speed", 1.0))
    is_en = voice.startswith("【EN")
    engine_name = "kokoro" if is_en else "vieneu"
    engine = get_tts(engine_name)
    sample_text = (
        "Hello! This is a preview of how my voice sounds in Shorts Studio."
        if is_en
        else "Xin chào các bạn! Đây là bản nghe thử giọng đọc thực tế."
    )
    preview_dir = PROJECTS_DIR / "_preview"
    preview_dir.mkdir(parents=True, exist_ok=True)
    out_file = preview_dir / "preview.wav"
    try:
        await run_in_threadpool(engine.synthesize, sample_text, voice, out_file, speed)
    except Exception as e:
        raise HTTPException(400, f"Lỗi nghe thử giọng: {e}")
    return {"url": f"/files/_preview/preview.wav?t={int(time.time() * 1000)}"}


@app.post("/api/extract-voice-url")
async def extract_voice_url(body: dict):
    from ..engines.legacy import use_legacy

    url = (body.get("url") or "").strip()
    name = (body.get("name") or "").strip()
    if not url or not name:
        raise HTTPException(400, "Vui lòng nhập URL và tên giọng")

    safe_name = re.sub(r"[^\w\-]", "_", name)
    dest_dir = Path(__file__).resolve().parents[2] / "long-tieng" / "voice"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_wav = dest_dir / f"{safe_name}.wav"
    tmp_tmpl = dest_dir / f"tmp_{safe_name}.%(ext)s"

    def _do():
        import yt_dlp
        import soundfile as sf
        use_legacy()
        import app

        ydl_opts = {
            "format": "bestaudio/best",
            "outtmpl": str(tmp_tmpl),
            "postprocessors": [{
                "key": "FFmpegExtractAudio",
                "preferredcodec": "wav",
                "preferredquality": "192",
            }],
            "quiet": True,
            "no_warnings": True,
        }
        with yt_dlp.YoutubeDL(ydl_opts) as ydl:
            ydl.download([url])

        raw_wav = dest_dir / f"tmp_{safe_name}.wav"
        if not raw_wav.exists():
            raise RuntimeError("Không tải được âm thanh từ link.")

        wav, sr, _ = app._load_ref_wav(raw_wav)
        best = app._best_speech_window(wav, sr, 8.0)
        best = app._peak_normalize(best)
        sf.write(str(dest_wav), best, sr)
        if raw_wav.exists():
            raw_wav.unlink()
        return safe_name

    try:
        created = await run_in_threadpool(_do)
        return {"status": "ok", "voice": created}
    except Exception as e:
        raise HTTPException(400, f"Trích xuất giọng thất bại: {e}")


@app.post("/api/upload-voice")
async def upload_voice(file: UploadFile, name: str = ""):
    from ..engines.legacy import use_legacy

    voice_name = name.strip() or Path(file.filename or "custom_voice").stem
    safe_name = re.sub(r"[^\w\-]", "_", voice_name)
    dest_dir = Path(__file__).resolve().parents[2] / "long-tieng" / "voice"
    dest_dir.mkdir(parents=True, exist_ok=True)
    dest_wav = dest_dir / f"{safe_name}.wav"
    tmp_dest = dest_dir / f"tmp_upload_{safe_name}.wav"

    with tmp_dest.open("wb") as f:
        shutil.copyfileobj(file.file, f)

    def _do():
        import soundfile as sf
        use_legacy()
        import app

        wav, sr, _ = app._load_ref_wav(tmp_dest)
        best = app._best_speech_window(wav, sr, 8.0)
        best = app._peak_normalize(best)
        sf.write(str(dest_wav), best, sr)
        if tmp_dest.exists():
            tmp_dest.unlink()
        return safe_name

    try:
        created = await run_in_threadpool(_do)
        return {"status": "ok", "voice": created}
    except Exception as e:
        raise HTTPException(400, f"Upload giọng thất bại: {e}")


@app.get("/api/meta")
def meta():
    from ..engines import tts_kokoro, tts_vieneu  # noqa: F401
    from ..engines.base import all_tts
    from ..render.captions import available_fonts

    read_styles = ["Bình thường", "Truyện ma", "Tin tức", "Kể chuyện", "Devlog / Chill", "Năng lượng"]

    all_v = {n: e.list_voices() for n, e in all_tts().items()}
    kokoro_v = all_v.get("kokoro", [])
    vieneu_v = all_v.get("vieneu", [])

    categories = {
        "🇻🇳 Tiếng Việt & Clone": vieneu_v,
        "🇺🇸 Tiếng Anh (Mỹ)": [v for v in kokoro_v if "am_" in v or "af_" in v or "blend_" in v],
        "🇬🇧 Tiếng Anh (Anh)": [v for v in kokoro_v if "bm_" in v or "bf_" in v],
    }

    user_home = Path.home()
    export_presets = [
        {"id": "project", "label": "📁 Thư mục dự án (Mặc định)", "path": "project"},
        {"id": "downloads", "label": "📥 Thư mục Downloads", "path": str(user_home / "Downloads")},
        {"id": "desktop", "label": "🖥️ Desktop (Màn hình chính)", "path": str(user_home / "Desktop")},
        {"id": "movies", "label": "🎬 Thư mục Phim (Movies)", "path": str(user_home / "Movies")},
    ]

    return {
        "voices": all_v,
        "categories": categories,
        "styles": read_styles,
        "fonts": available_fonts(),
        "export_presets": export_presets,
    }


_web = Path(__file__).resolve().parents[1] / "web" / "dist"
if _web.exists():
    app.mount("/", StaticFiles(directory=str(_web), html=True), name="web")
