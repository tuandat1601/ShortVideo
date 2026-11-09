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
    offset: float = 0.0             # mốc bắt đầu giọng trên timeline (giây)


class VoiceSegment(BaseModel):
    """Một đoạn thoại trên timeline: hỗ trợ kịch bản riêng, giọng riêng, thời điểm riêng."""
    id: str = Field(default_factory=lambda: uuid.uuid4().hex[:8])
    text: str = ""
    voice: str = "【EN Devlog Trẻ / Độc quyền】blend_young_devlog"
    engine: Literal["kokoro", "vieneu"] = "kokoro"
    style: str = "Devlog / Chill"
    speed: float = 1.0
    start: float = 0.0          # mốc bắt đầu trên timeline (giây)
    dur: float = 0.0            # thời lượng sau khi đọc (giây)
    file: str | None = None     # đường dẫn file wav riêng của đoạn này
    words: list[Word] = Field(default_factory=list)


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
    z_order: int = 0              # thứ tự lớp: số càng lớn càng nằm đè lên trên
    # Căn góc / Reframe / Crop cho video ngang (quay màn hình 16:9 -> dọc 9:16)
    crop_x: float = 50.0          # 0 = mép trái, 50 = giữa, 100 = mép phải
    crop_y: float = 50.0          # 0 = đỉnh trên, 50 = giữa, 100 = đáy dưới
    crop_scale: float = 100.0     # 100 = vừa khung, >100 = zoom cận cảnh vào vùng chọn


class Project(BaseModel):
    id: str
    name: str = "Untitled"
    width: int = 1080
    height: int = 1920
    fps: int = 30
    bg_color: str = "#0B0B12"
    script: str = ""
    voice: VoiceSettings = Field(default_factory=VoiceSettings)
    voice_segments: list[VoiceSegment] = Field(default_factory=list)
    caption: CaptionStyle = Field(default_factory=CaptionStyle)
    words: list[Word] = Field(default_factory=list)
    voice_file: str | None = None   # tương đối trong thư mục project
    bgm_file: str | None = None     # tương đối trong thư mục project (vd "media/bgm.mp3")
    bgm_volume: float = 0.25        # âm lượng nhạc nền (0.0 đến 1.0)
    bgm_offset: float = 0.0         # mốc bắt đầu BGM trên timeline (giây)
    export_dir: str | None = None   # thư mục xuất file tùy chọn (vd "~/Downloads", "~/Desktop")
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
        ends = (
            [w.end for w in self.words]
            + [s.start + s.dur for s in self.voice_segments]
            + [c.start + c.dur for c in self.clips]
        )
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
