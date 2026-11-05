"""Project model: một file project.json là nguồn sự thật duy nhất.

UI, CLI (agent) và renderer đều chỉ đọc/ghi model này.
"""
from __future__ import annotations

import json
import uuid
from pathlib import Path
from typing import Literal

from pydantic import BaseModel, Field

STUDIO_ROOT = Path(__file__).resolve().parents[1]
PROJECTS_DIR = STUDIO_ROOT / "projects"


class Word(BaseModel):
    text: str
    start: float
    end: float
    emph: bool = False  # từ khóa -> đổi màu


class CaptionStyle(BaseModel):
    font: str = "Impact"
    size: int = 120
    color: str = "#FFFFFF"
    emph_color: str = "#2EE6FF"
    stroke_color: str = "#000000"
    stroke_width: int = 10
    y_pct: float = 55.0          # vị trí dọc (% chiều cao), 50 = giữa
    max_words: int = 2           # số từ hiện cùng lúc
    uppercase: bool = False
    effect: Literal["none", "pop_in"] = "pop_in"


class VoiceSettings(BaseModel):
    engine: Literal["kokoro", "vieneu"] = "kokoro"
    voice: str = "【EN Devlog Trẻ / Độc quyền】blend_young_devlog"
    speed: float = 1.0
    style: str = "Devlog / Chill"   # preset hậu kỳ của dub.READ_STYLES


class Clip(BaseModel):
    """Clip trên timeline (hỗ trợ cả video nền và lớp phủ icon/ảnh/sticker)."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    track: Literal["video", "overlay"] = "video"
    src: str                      # đường dẫn tương đối trong media/
    start: float = 0.0            # vị trí trên timeline
    dur: float = 2.0
    in_point: float = 0.0         # cắt từ giây nào của file nguồn
    fit: Literal["cover", "contain_blur", "contain"] = "cover"
    effect: Literal["none", "zoom_in", "zoom_out", "fade", "flash", "dim_blur", "spotlight"] = "none"
    dim_bg: bool = False          # Nếu True (hoặc effect=="spotlight"): tự làm tối mờ nền phía sau khi clip/overlay này hiện
    # Toạ độ và kích thước cho overlay / icon (% màn hình)
    x_pct: float = 50.0           # 50 = giữa
    y_pct: float = 30.0           # vị trí dọc
    scale_pct: float = 35.0       # chiều rộng so với chiều rộng màn hình (%)


class Project(BaseModel):
    id: str
    name: str = "Untitled"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    bg_color: str = "#0B0B12"
    script: str = ""
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    caption: CaptionStyle = Field(default_factory=CaptionStyle)
    words: list[Word] = Field(default_factory=list)
    voice_file: str | None = None   # tương đối trong thư mục project
    clips: list[Clip] = Field(default_factory=list)

    # ---- đường dẫn ----
    @property
    def dir(self) -> Path:
        return PROJECTS_DIR / self.id

    @property
    def media_dir(self) -> Path:
        return self.dir / "media"

    @property
    def build_dir(self) -> Path:
        return self.dir / "build"

    @property
    def duration(self) -> float:
        ends = [w.end for w in self.words] + [c.start + c.dur for c in self.clips]
        return max(ends) if ends else 0.0

    # ---- lưu / mở ----
    def save(self) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        self.media_dir.mkdir(exist_ok=True)
        (self.dir / "project.json").write_text(
            self.model_dump_json(indent=2), encoding="utf-8"
        )

    @classmethod
    def load(cls, project_id: str) -> "Project":
        path = PROJECTS_DIR / project_id / "project.json"
        if not path.exists():
            raise FileNotFoundError(f"Không thấy project '{project_id}'")
        return cls.model_validate(json.loads(path.read_text(encoding="utf-8")))

    @classmethod
    def create(cls, name: str = "Untitled", **kw) -> "Project":
        pid = uuid.uuid4().hex[:8]
        proj = cls(id=pid, name=name, **kw)
        proj.save()
        return proj


def list_projects() -> list[dict]:
    PROJECTS_DIR.mkdir(parents=True, exist_ok=True)
    out = []
    for d in sorted(PROJECTS_DIR.iterdir()):
        f = d / "project.json"
        if f.exists():
            try:
                p = json.loads(f.read_text(encoding="utf-8"))
                out.append({"id": p["id"], "name": p.get("name", "")})
            except Exception:
                continue
    return out
