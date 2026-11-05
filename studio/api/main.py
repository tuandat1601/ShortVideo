"""FastAPI: lớp mỏng bọc core. Chạy:  uvicorn studio.api.main:app --port 8000"""
from __future__ import annotations

import shutil
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
async def make_voice(pid: str):
    from ..core.workflows.voiceover import build_voiceover

    proj = _load(pid)
    try:
        return await run_in_threadpool(build_voiceover, proj)
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
async def render(pid: str):
    from ..render.compiler import render_project

    proj = _load(pid)
    try:
        out = await run_in_threadpool(render_project, proj)
    except Exception as e:
        raise HTTPException(400, str(e))
    return {"url": f"/files/{pid}/out/{Path(out).name}"}


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


@app.get("/api/meta")
def meta():
    from ..engines import tts_kokoro  # noqa: F401
    from ..engines.base import all_tts
    from ..engines.legacy import use_legacy
    from ..render.captions import available_fonts

    use_legacy()
    from dub import READ_STYLES  # type: ignore

    return {
        "voices": {n: e.list_voices() for n, e in all_tts().items()},
        "styles": list(READ_STYLES.keys()),
        "fonts": available_fonts(),
    }


_web = Path(__file__).resolve().parents[1] / "web" / "dist"
if _web.exists():
    app.mount("/", StaticFiles(directory=str(_web), html=True), name="web")
