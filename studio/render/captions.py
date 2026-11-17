"""Vẽ chữ từng từ thành PNG trong suốt (ffmpeg Homebrew không có libass)."""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from ..core.project import CaptionStyle, Project, Word

FONT_FILES = {
    "Impact": "/System/Library/Fonts/Supplemental/Impact.ttf",
    "Arial Black": "/System/Library/Fonts/Supplemental/Arial Black.ttf",
    "DIN Condensed": "/System/Library/Fonts/Supplemental/DIN Condensed Bold.ttf",
    "Courier Bold": "/System/Library/Fonts/Supplemental/Courier New Bold.ttf",
}


def available_fonts() -> list[str]:
    return [n for n, p in FONT_FILES.items() if Path(p).exists()] or ["Impact"]


def _font(style: CaptionStyle) -> ImageFont.FreeTypeFont:
    path = FONT_FILES.get(style.font) or FONT_FILES["Impact"]
    try:
        return ImageFont.truetype(path, style.size)
    except OSError:
        return ImageFont.load_default()


@dataclass
class CaptionGroup:
    words: list[Word]

    @property
    def start(self) -> float:
        return self.words[0].start

    @property
    def end(self) -> float:
        return self.words[-1].end


def group_words(words: list[Word], max_words: int) -> list[CaptionGroup]:
    """Gom từ thành nhóm; ngắt nhóm sau dấu câu."""
    groups: list[CaptionGroup] = []
    cur: list[Word] = []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or w.text.rstrip()[-1:] in ".!?,;:":
            groups.append(CaptionGroup(cur))
            cur = []
    if cur:
        groups.append(CaptionGroup(cur))
    return groups


def hex_to_rgba(hex_color: str, default_alpha: int = 255) -> tuple[int, int, int, int]:
    h = (hex_color or "").strip().lstrip("#")
    if len(h) == 6:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), default_alpha
    elif len(h) == 8:
        return int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16), int(h[6:8], 16)
    elif len(h) == 3:
        return int(h[0] * 2, 16), int(h[1] * 2, 16), int(h[2] * 2, 16), default_alpha
    return 0, 0, 0, default_alpha


def render_group(proj: Project, group: CaptionGroup, dest: Path) -> None:
    st = proj.caption
    img = Image.new("RGBA", (proj.width, proj.height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(img)
    font = _font(st)

    parts = []
    for w in group.words:
        t = w.text.upper() if st.uppercase else w.text
        parts.append((t, st.emph_color if w.emph else st.color))

    space = draw.textlength(" ", font=font)
    widths = [draw.textlength(t, font=font) for t, _ in parts]
    max_w = proj.width * 0.9
    total = sum(widths) + space * (len(parts) - 1)

    # nếu quá rộng thì xuống dòng mỗi từ
    lines: list[list[tuple[str, str, float]]]
    if total <= max_w:
        lines = [[(t, c, wd) for (t, c), wd in zip(parts, widths)]]
    else:
        lines = [[(t, c, wd)] for (t, c), wd in zip(parts, widths)]

    line_h = int(st.size * 1.15)
    block_h = line_h * len(lines)
    y = int(proj.height * st.y_pct / 100 - block_h / 2)

    pad_x = getattr(st, "box_padding", 20) or 20
    pad_y = int(pad_x * 0.55)
    box_style = getattr(st, "box_style", "none") or "none"
    box_rgba = hex_to_rgba(getattr(st, "box_color", "#000000B0") or "#000000B0", 180)

    for line in lines:
        lw = sum(x[2] for x in line) + space * (len(line) - 1)
        x = (proj.width - lw) / 2

        if box_style in ("pill", "card"):
            rx0 = x - pad_x
            ry0 = y - pad_y
            rx1 = x + lw + pad_x
            ry1 = y + line_h + pad_y
            rad = int((ry1 - ry0) / 2) if box_style == "pill" else 18
            draw.rounded_rectangle([rx0, ry0, rx1, ry1], radius=rad, fill=box_rgba)

        for text, color, wd in line:
            if box_style == "highlight":
                hx0 = x - pad_x * 0.5
                hy0 = y - pad_y * 0.5
                hx1 = x + wd + pad_x * 0.5
                hy1 = y + line_h + pad_y * 0.5
                draw.rounded_rectangle([hx0, hy0, hx1, hy1], radius=14, fill=box_rgba)

            draw.text(
                (x, y), text, font=font, fill=color,
                stroke_width=st.stroke_width, stroke_fill=st.stroke_color,
            )
            x += wd + space
        y += line_h
    img.save(dest)


def render_caption_frames(proj: Project) -> Path:
    """Sinh PNG + concat.txt (có khoảng trống trong suốt). Trả về đường dẫn concat.txt."""
    out = proj.build_dir / "captions"
    out.mkdir(parents=True, exist_ok=True)
    for old in out.glob("*.png"):
        old.unlink()

    blank = out / "blank.png"
    Image.new("RGBA", (proj.width, proj.height), (0, 0, 0, 0)).save(blank)

    groups = group_words(proj.words, proj.caption.max_words)
    total = max(proj.duration, 0.1)
    lines: list[str] = []
    cursor = 0.0
    last_png = blank
    for i, g in enumerate(groups):
        # chữ giữ tới khi nhóm sau bắt đầu (không nhấp nháy giữa các từ)
        nxt = groups[i + 1].start if i + 1 < len(groups) else g.end + 0.25
        start = max(g.start, cursor)
        end = max(min(nxt, g.end + 0.6), start + 0.05)
        if start > cursor + 1e-3:
            lines += [f"file '{blank.name}'", f"duration {start - cursor:.3f}"]
        png = out / f"c{i:04d}.png"
        render_group(proj, g, png)
        lines += [f"file '{png.name}'", f"duration {end - start:.3f}"]
        cursor = end
        last_png = png
    if cursor < total:
        lines += [f"file '{blank.name}'", f"duration {total - cursor:.3f}"]
    lines.append(f"file '{blank.name}'")  # concat demuxer cần lặp file cuối
    concat = out / "concat.txt"
    concat.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return concat
