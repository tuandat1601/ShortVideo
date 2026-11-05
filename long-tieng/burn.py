#!/usr/bin/env python3
"""Lát E: vẽ sub bằng Pillow + overlay ffmpeg (Homebrew ffmpeg không có libass)."""
from __future__ import annotations

import base64
import html
from pathlib import Path

from stt import parse_srt
from video_job import Job, _run_cmd, probe, require_ffmpeg

PRESETS = {
    "Dưới": (50.0, 88.0),
    "Giữa": (50.0, 50.0),
    "Trên": (50.0, 12.0),
}

BG_ALPHA = 242  # ~95% — mặc định đậm để che chữ gốc
DEFAULT_TEXT_COLOR = "#FFFFFF"
DEFAULT_FONT = "Arial Bold"
DEFAULT_FONT_SIZE = 48
MIN_FONT_SIZE = 20
MAX_FONT_SIZE = 120

# name → (path, face index, CSS fallback, hỗ trợ dấu Việt tốt?)
_FONT_SPECS: dict[str, tuple[Path, int, str, bool]] = {
    "Arial Bold": (
        Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
        0,
        "Arial, Helvetica, sans-serif",
        True,
    ),
    "Arial Unicode": (
        Path("/System/Library/Fonts/Supplemental/Arial Unicode.ttf"),
        0,
        "Arial, 'Arial Unicode MS', sans-serif",
        True,
    ),
    "Arial Bold Italic": (
        Path("/System/Library/Fonts/Supplemental/Arial Bold Italic.ttf"),
        0,
        "Arial, Helvetica, sans-serif",
        True,
    ),
    "Arial Black": (
        Path("/System/Library/Fonts/Supplemental/Arial Black.ttf"),
        0,
        "'Arial Black', Gadget, sans-serif",
        True,
    ),
    "Helvetica Bold": (
        Path("/System/Library/Fonts/Helvetica.ttc"),
        1,
        "Helvetica, Arial, sans-serif",
        True,
    ),
    "Georgia Bold": (
        Path("/System/Library/Fonts/Supplemental/Georgia Bold.ttf"),
        0,
        "Georgia, 'Times New Roman', serif",
        True,
    ),
    "Comic Sans Bold": (
        Path("/System/Library/Fonts/Supplemental/Comic Sans MS Bold.ttf"),
        0,
        "'Comic Sans MS', 'Chalkboard SE', cursive",
        True,
    ),
    "Impact (EN)": (
        Path("/System/Library/Fonts/Supplemental/Impact.ttf"),
        0,
        "Impact, Haettenschweiler, sans-serif",
        False,
    ),
    "DIN Condensed (EN)": (
        Path("/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf"),
        0,
        "'Arial Narrow', Arial, sans-serif",
        False,
    ),
}

_FONT_FALLBACKS = (
    Path("/System/Library/Fonts/Supplemental/Arial Bold.ttf"),
    Path("/System/Library/Fonts/Supplemental/Arial.ttf"),
    Path("/System/Library/Fonts/Helvetica.ttc"),
    Path("/Library/Fonts/Arial.ttf"),
)


def clamp_opacity(value: float) -> float:
    return min(100.0, max(40.0, float(value)))


def opacity_alpha(pct: float) -> int:
    return int(round(255 * clamp_opacity(pct) / 100.0))

PLACEHOLDER_HTML = (
    "<div id='sub-stage' class='sub-stage empty'>"
    "<p>Bấm <b>5 Xuất</b> hoặc <b>Xem khung</b> — kéo ô chữ trên hình này, "
    "kéo tay cầm hai bên để đổi độ dài. Không kéo video Mp4 cuối.</p>"
    "</div>"
)


def available_fonts() -> list[str]:
    names = [
        name
        for name, (path, _idx, _css, _vie) in _FONT_SPECS.items()
        if path.exists()
    ]
    return names or [DEFAULT_FONT]


def clamp_pct(value: float) -> float:
    return min(95.0, max(5.0, float(value)))


def clamp_width(value: float) -> float:
    return min(92.0, max(30.0, float(value)))


def clamp_font_size(value: float | int | None) -> int:
    if value is None:
        return DEFAULT_FONT_SIZE
    try:
        return int(min(MAX_FONT_SIZE, max(MIN_FONT_SIZE, float(value))))
    except (TypeError, ValueError):
        return DEFAULT_FONT_SIZE


def parse_layout(
    raw: str, default: tuple[float, float, float] = (50.0, 88.0, 70.0)
) -> tuple[float, float, float]:
    try:
        parts = (raw or "").replace("%", "").split(",")
        x = clamp_pct(float(parts[0]))
        y = clamp_pct(float(parts[1]))
        w = clamp_width(float(parts[2])) if len(parts) > 2 else default[2]
        return x, y, w
    except (ValueError, TypeError, IndexError):
        return default


def parse_xy(raw: str, default: tuple[float, float] = (50.0, 88.0)) -> tuple[float, float]:
    x, y, _w = parse_layout(
        raw, default=(default[0], default[1], 70.0)
    )
    return x, y


def parse_color(raw: str) -> tuple[int, int, int]:
    s = (raw or "#000000").strip()
    if s.startswith("rgb"):
        nums = "".join(ch if ch.isdigit() or ch == "," else " " for ch in s)
        parts = [int(p) for p in nums.replace(" ", "").split(",") if p]
        if len(parts) >= 3:
            return parts[0] % 256, parts[1] % 256, parts[2] % 256
        return (0, 0, 0)
    s = s.lstrip("#")
    if len(s) == 3:
        s = "".join(ch * 2 for ch in s)
    if len(s) != 6:
        return (0, 0, 0)
    return int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16)


def font_css(name: str | None) -> str:
    key = (name or DEFAULT_FONT).strip()
    spec = _FONT_SPECS.get(key)
    if spec:
        return spec[2]
    return "Arial, Helvetica, sans-serif"


def _font(size: int, name: str | None = None):
    from PIL import ImageFont

    size = clamp_font_size(size)
    key = (name or DEFAULT_FONT).strip()
    candidates: list[tuple[Path, int]] = []
    if key in _FONT_SPECS:
        path, idx, _css, _vie = _FONT_SPECS[key]
        candidates.append((path, idx))
    candidates.extend((path, 0) for path in _FONT_FALLBACKS)
    seen: set[str] = set()
    for path, idx in candidates:
        mark = f"{path}:{idx}"
        if mark in seen or not path.exists():
            continue
        seen.add(mark)
        try:
            return ImageFont.truetype(str(path), size=size, index=idx)
        except OSError:
            continue
    return ImageFont.load_default()


def wrap_to_width(text: str, font, max_px: int, max_lines: int = 3) -> str:
    from PIL import Image, ImageDraw

    dummy = Image.new("RGBA", (8, 8))
    draw = ImageDraw.Draw(dummy)

    def line_w(s: str) -> int:
        if not s:
            return 0
        box = draw.textbbox((0, 0), s, font=font)
        return int(box[2] - box[0])

    words = (text or "").split()
    if not words:
        return ""
    lines: list[str] = []
    cur = words[0]
    rest_words = words[1:]
    i = 0
    while i < len(rest_words):
        word = rest_words[i]
        trial = f"{cur} {word}"
        if line_w(trial) <= max_px:
            cur = trial
            i += 1
            continue
        lines.append(cur)
        cur = word
        i += 1
        if len(lines) >= max_lines - 1:
            leftover = " ".join([cur] + rest_words[i:])
            while leftover and line_w(leftover) > max_px:
                leftover = leftover[:-1].rstrip()
            lines.append(leftover or cur)
            return "\n".join(lines[:max_lines])
    lines.append(cur)
    return "\n".join(lines[:max_lines])


def _wrap(text: str, max_chars: int = 36) -> str:
    return wrap_to_width(text, _font(32, DEFAULT_FONT), max(120, max_chars * 14), 2)


def srt_for_burn(job: Job, *, require_final: bool = False) -> str:
    if require_final:
        if not job.final_srt.exists():
            raise RuntimeError("Chưa khóa final.srt.")
        return job.final_srt.read_text(encoding="utf-8")
    for path in (job.final_srt, job.target_srt, job.orig_srt):
        if path.exists():
            raw = path.read_text(encoding="utf-8").strip()
            if raw:
                return raw
    raise RuntimeError("Chưa có sub. Tab 2 Sub trước.")


def render_cue_png(
    text: str,
    width: int,
    height: int,
    x_pct: float,
    y_pct: float,
    dest: Path,
    *,
    bg: bool = False,
    bg_color: str = "#000000",
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: int | None = None,
    font=None,
    box_w_pct: float = 70.0,
    bg_opacity: float = 95.0,
) -> Path:
    from PIL import Image, ImageDraw

    dest.parent.mkdir(parents=True, exist_ok=True)
    img = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    if font_size is None:
        size = 48 if min(width, height) >= 720 else 32
    else:
        size = clamp_font_size(font_size)
    font = font or _font(size, font_name)
    fill = (*parse_color(text_color), 255)
    pad_x, pad_y = max(size // 3, 12), max(size // 5, 8)
    box_w = int(width * clamp_width(box_w_pct) / 100.0)
    inner = max(box_w - 2 * pad_x, 40)
    wrapped = wrap_to_width(text, font, inner, 3)
    cx = int(width * clamp_pct(x_pct) / 100.0)
    cy = int(height * clamp_pct(y_pct) / 100.0)
    bbox = draw.multiline_textbbox((0, 0), wrapped, font=font, align="center", spacing=6)
    tw, th = bbox[2] - bbox[0], bbox[3] - bbox[1]
    bh = th + 2 * pad_y
    left = max(0, min(cx - box_w // 2, width - box_w))
    top = max(0, min(cy - bh // 2, height - bh))
    if bg:
        rgb = parse_color(bg_color)
        draw.rounded_rectangle(
            (left, top, left + box_w, top + bh),
            radius=max(size // 5, 8),
            fill=(*rgb, opacity_alpha(bg_opacity)),
        )
    stroke = max(size // 12, 2)
    tx = left + (box_w - tw) // 2
    ty = top + pad_y
    draw.multiline_text(
        (tx, ty),
        wrapped,
        font=font,
        fill=fill,
        stroke_width=stroke,
        stroke_fill=(0, 0, 0, 255),
        align="center",
        spacing=6,
    )
    img.save(dest, compress_level=1)
    return dest


def write_overlays(
    job: Job,
    srt_raw: str,
    x_pct: float,
    y_pct: float,
    width: int,
    height: int,
    *,
    bg: bool = False,
    bg_color: str = "#000000",
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: int | None = None,
    box_w_pct: float = 70.0,
    bg_opacity: float = 95.0,
) -> list[tuple[float, float, Path]]:
    overlay_dir = job.dir / "subs"
    if overlay_dir.exists():
        for old in overlay_dir.glob("*.png"):
            old.unlink()
    overlay_dir.mkdir(parents=True, exist_ok=True)
    rows = parse_srt(srt_raw)
    if font_size is None:
        size = 48 if min(width, height) >= 720 else 32
    else:
        size = clamp_font_size(font_size)
    font = _font(size, font_name)
    out: list[tuple[float, float, Path]] = []
    for i, (start, end, text) in enumerate(rows, 1):
        png = overlay_dir / f"{i:04d}.png"
        render_cue_png(
            text,
            width,
            height,
            x_pct,
            y_pct,
            png,
            bg=bg,
            bg_color=bg_color,
            text_color=text_color,
            font_name=font_name,
            font_size=size,
            font=font,
            box_w_pct=box_w_pct,
            bg_opacity=bg_opacity,
        )
        out.append((start, end, png))
    (job.dir / "style.ass").write_text(
        f"# overlay x={x_pct} y={y_pct} w={box_w_pct} bg={int(bg)} "
        f"op={bg_opacity} bg_color={bg_color} text={text_color} "
        f"font={font_name} size={size} cues={len(out)}\n",
        encoding="utf-8",
    )
    return out


def prepare_style(
    job: Job,
    x_pct: float,
    y_pct: float,
    srt_raw: str | None = None,
    *,
    bg: bool = False,
    bg_color: str = "#000000",
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: int | None = None,
    box_w_pct: float = 70.0,
    bg_opacity: float = 95.0,
    require_final: bool = True,
):
    info = probe(job.source)
    raw = srt_raw or srt_for_burn(job, require_final=require_final)
    width = info["width"] or 1280
    height = info["height"] or 720
    overlays = write_overlays(
        job,
        raw,
        x_pct,
        y_pct,
        width,
        height,
        bg=bg,
        bg_color=bg_color,
        text_color=text_color,
        font_name=font_name,
        font_size=font_size,
        box_w_pct=box_w_pct,
        bg_opacity=bg_opacity,
    )
    return overlays, info


def extract_frame(job: Job, at_sec: float | None = None) -> tuple[Path, float]:
    ffmpeg, _ = require_ffmpeg()
    info = probe(job.source)
    duration = max(float(info["duration"] or 0.0), 0.1)
    if at_sec is None:
        at_sec = max(duration * 0.4, 0.1)
    at_sec = min(max(float(at_sec), 0.0), max(duration - 0.05, 0.0))
    frame = job.dir / "_frame.jpg"
    _run_cmd(
        [
            ffmpeg,
            "-y",
            "-ss",
            f"{at_sec:.3f}",
            "-i",
            str(job.source),
            "-frames:v",
            "1",
            str(frame),
        ]
    )
    if not frame.exists():
        raise RuntimeError("Không tách được khung preview.")
    return frame, at_sec


def cue_at(job: Job, at_sec: float) -> str:
    rows = parse_srt(srt_for_burn(job, require_final=False))
    if not rows:
        return "…"
    for start, end, text in rows:
        if start - 0.05 <= at_sec <= end + 0.05:
            return text
    nearest = min(rows, key=lambda row: abs(row[0] - at_sec))
    return nearest[2]


def stage_html(
    frame: Path | None,
    text: str,
    x_pct: float,
    y_pct: float,
    bg: bool = False,
    bg_color: str = "#000000",
    box_w_pct: float = 70.0,
    bg_opacity: float = 95.0,
    *,
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: int | float | None = None,
) -> str:
    if frame is None or not Path(frame).exists():
        return PLACEHOLDER_HTML
    blob = base64.b64encode(Path(frame).read_bytes()).decode("ascii")
    x_pct, y_pct = clamp_pct(x_pct), clamp_pct(y_pct)
    box_w_pct = clamp_width(box_w_pct)
    size = clamp_font_size(font_size)
    # Preview nhỏ hơn video — scale ~0.45 để gần đúng cỡ burn.
    preview_px = max(12, int(round(size * 0.45)))
    rgb = parse_color(bg_color)
    fill = parse_color(text_color or DEFAULT_TEXT_COLOR)
    alpha = clamp_opacity(bg_opacity) / 100.0
    bg_css = (
        f"background:rgba({rgb[0]},{rgb[1]},{rgb[2]},{alpha:.2f});"
        if bg
        else "background:rgba(0,0,0,0.35);"
    )
    text_css = (
        f"color:rgb({fill[0]},{fill[1]},{fill[2]});"
        f"font-family:{font_css(font_name)};"
        f"font-size:{preview_px}px;"
        f"font-weight:700;"
    )
    safe = html.escape((text or "").strip() or "…").replace("\n", "<br>")
    return (
        f"<div id='sub-stage' class='sub-stage'>"
        f"<img src='data:image/jpeg;base64,{blob}' alt='khung' draggable='false'/>"
        f"<div id='sub-box' class='sub-box' style='left:{x_pct:.1f}%;top:{y_pct:.1f}%;"
        f"width:{box_w_pct:.1f}%;{bg_css}{text_css}'>"
        f"<span class='sub-handle sub-handle-w'></span>"
        f"{safe}"
        f"<span class='sub-handle sub-handle-e'></span>"
        f"</div></div>"
    )


def preview_frame(
    job: Job,
    x_pct: float,
    y_pct: float,
    at_sec: float | None = None,
    *,
    bg: bool = False,
    bg_color: str = "#000000",
):
    from PIL import Image

    overlays, info = prepare_style(
        job, x_pct, y_pct, bg=bg, bg_color=bg_color, require_final=False
    )
    frame, at_sec = extract_frame(job, at_sec if at_sec is not None else None)
    base = Image.open(frame).convert("RGBA")
    active = None
    for start, end, png in overlays:
        if start - 0.05 <= at_sec <= end + 0.05:
            active = png
            break
    if active is None and overlays:
        active = min(overlays, key=lambda row: abs(row[0] - at_sec))[2]
    if active is not None:
        overlay = Image.open(active).convert("RGBA")
        if overlay.size != base.size:
            overlay = overlay.resize(base.size)
        base = Image.alpha_composite(base, overlay)
    dest = job.preview_jpg
    base.convert("RGB").save(dest, quality=90)
    return dest


def _concat_quote(name: str) -> str:
    return "'" + name.replace("'", r"'\''") + "'"


def write_concat_list(
    overlay_dir: Path,
    overlays: list[tuple[float, float, Path]],
    duration: float,
    width: int,
    height: int,
) -> Path:
    from PIL import Image

    blank = overlay_dir / "_blank.png"
    Image.new("RGBA", (width, height), (0, 0, 0, 0)).save(blank, compress_level=1)
    lines = ["ffconcat version 1.0"]
    t = 0.0
    last = blank.name
    min_dur = 0.04
    for start, end, png in overlays:
        start = max(float(start), 0.0)
        end = max(float(end), start + min_dur)
        if start < t:
            start = t
            if end <= start:
                continue
        if start > t + 0.01:
            lines.append(f"file {_concat_quote(blank.name)}")
            lines.append(f"duration {start - t:.4f}")
            last = blank.name
        lines.append(f"file {_concat_quote(png.name)}")
        lines.append(f"duration {end - start:.4f}")
        last = png.name
        t = end
    if duration > t + 0.01:
        lines.append(f"file {_concat_quote(blank.name)}")
        lines.append(f"duration {duration - t:.4f}")
        last = blank.name
    lines.append(f"file {_concat_quote(last)}")
    dest = overlay_dir / "concat.txt"
    dest.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return dest


def _mux_args(dest: Path, *, hardware: bool, width: int, height: int) -> list[str]:
    audio = ["-c:a", "aac", "-b:a", "192k", "-shortest", "-movflags", "+faststart"]
    if hardware:
        pixels = max(width * height, 1)
        kbps = int(min(12000, max(4000, pixels / 200)))
        return [
            "-c:v",
            "h264_videotoolbox",
            "-b:v",
            f"{kbps}k",
            "-pix_fmt",
            "yuv420p",
            *audio,
            str(dest),
        ]
    return [
        "-c:v",
        "libx264",
        "-preset",
        "veryfast",
        "-crf",
        "20",
        "-pix_fmt",
        "yuv420p",
        *audio,
        str(dest),
    ]


def export_final(
    job: Job,
    x_pct: float,
    y_pct: float,
    *,
    bg: bool = False,
    bg_color: str = "#000000",
    text_color: str = DEFAULT_TEXT_COLOR,
    font_name: str = DEFAULT_FONT,
    font_size: int | None = None,
    box_w_pct: float = 70.0,
    bg_opacity: float = 95.0,
):
    ffmpeg, _ = require_ffmpeg()
    if not job.voice_new.exists():
        raise RuntimeError("Chưa có voice_new.wav. Cửa 5 trước.")
    overlays, info = prepare_style(
        job,
        x_pct,
        y_pct,
        bg=bg,
        bg_color=bg_color,
        text_color=text_color,
        font_name=font_name,
        font_size=font_size,
        box_w_pct=box_w_pct,
        bg_opacity=bg_opacity,
        require_final=True,
    )
    dest = job.final_mp4
    dest.parent.mkdir(parents=True, exist_ok=True)
    width = info["width"] or 1280
    height = info["height"] or 720
    duration = max(float(info["duration"] or 0.0), 0.1)
    cmd = [ffmpeg, "-y", "-i", str(job.source), "-i", str(job.voice_new)]
    if overlays:
        concat = write_concat_list(
            job.dir / "subs", overlays, duration, width, height
        )
        cmd.extend(["-f", "concat", "-safe", "0", "-i", str(concat)])
        cmd.extend(
            [
                "-filter_complex",
                "[2:v]format=rgba[sub];"
                "[0:v][sub]overlay=0:0:eof_action=pass:repeatlast=0[v];"
                "[v]format=yuv420p[vout]",
                "-map",
                "[vout]",
                "-map",
                "1:a:0",
            ]
        )
    else:
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
    try:
        _run_cmd(cmd + _mux_args(dest, hardware=True, width=width, height=height))
    except RuntimeError:
        _run_cmd(cmd + _mux_args(dest, hardware=False, width=width, height=height))
    if not dest.exists() or dest.stat().st_size < 1000:
        raise RuntimeError("Xuất mp4 thất bại.")
    return dest
