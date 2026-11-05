"""Compile project.json -> ffmpeg -> mp4."""
from __future__ import annotations

import subprocess
from pathlib import Path

from ..core.project import Project
from .captions import render_caption_frames

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi:\n{proc.stderr[-1200:]}")


def build_command(proj: Project, out: Path, concat: Path | None, encoder: str) -> list[str]:
    W, H, fps = proj.width, proj.height, proj.fps
    dur = max(proj.duration, 0.5) + 0.3
    cmd = [
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"color=c={proj.bg_color.lstrip('#')}:s={W}x{H}:r={fps}:d={dur:.3f}",
    ]
    n_in = 1
    filters: list[str] = []
    last = "0:v"

    video_clips = [c for c in proj.clips if getattr(c, "track", "video") == "video"]
    overlay_clips = [c for c in proj.clips if getattr(c, "track", "video") == "overlay"]

    # 1. Base video track
    for clip in sorted(video_clips, key=lambda c: c.start):
        src = proj.dir / clip.src
        if not src.exists():
            raise FileNotFoundError(f"Thiếu media: {clip.src}")
        if src.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop", "1", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        else:
            cmd += ["-ss", f"{clip.in_point:.3f}", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        i = n_in
        n_in += 1

        fx = []
        if clip.fit == "contain_blur":
            base_f = (
                f"[{i}:v]split[a{i}][b{i}];"
                f"[a{i}]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},boxblur=30:5[bg{i}];"
                f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,fps={fps}[vraw{i}]"
            )
            filters.append(base_f)
            v_in = f"vraw{i}"
        else:
            filters.append(
                f"[{i}:v]scale={W}:{H}:force_original_aspect_ratio=increase,crop={W}:{H},fps={fps}[vraw{i}]"
            )
            v_in = f"vraw{i}"

        # Effects
        if clip.effect == "zoom_in":
            fx.append(f"scale=eval=frame:w='{W}*(1.0+0.12*t/{max(clip.dur,0.1):.3f})':h='{H}*(1.0+0.12*t/{max(clip.dur,0.1):.3f})',crop={W}:{H}")
        elif clip.effect == "zoom_out":
            fx.append(f"scale=eval=frame:w='{W}*(1.12-0.12*t/{max(clip.dur,0.1):.3f})':h='{H}*(1.12-0.12*t/{max(clip.dur,0.1):.3f})',crop={W}:{H}")
        elif clip.effect == "fade":
            fx.append("fade=t=in:st=0:d=0.35")
        elif clip.effect == "flash":
            fx.append("fade=t=in:st=0:d=0.18:color=white")
        elif clip.effect == "dim_blur":
            fx.append("boxblur=20:4,eq=brightness=-0.32:contrast=1.05")

        fx.append(f"setpts=PTS-STARTPTS+{clip.start:.3f}/TB")
        filters.append(f"[{v_in}]{','.join(fx)}[v{i}]")

        out_lbl = f"o{i}"
        filters.append(
            f"[{last}][v{i}]overlay=eof_action=pass:"
            f"enable='between(t,{clip.start:.3f},{clip.start + clip.dur:.3f})'[{out_lbl}]"
        )
        last = out_lbl

    # 2. Overlay / Icon / Sticker track
    for clip in sorted(overlay_clips, key=lambda c: c.start):
        src = proj.dir / clip.src
        if not src.exists():
            continue
        if src.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop", "1", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        else:
            cmd += ["-ss", f"{clip.in_point:.3f}", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        i = n_in
        n_in += 1

        ow = max(int(W * clip.scale_pct / 100), 40)
        if ow % 2 != 0:
            ow += 1
        fx_ov = [f"scale={ow}:-2", f"fps={fps}"]
        if clip.effect == "fade":
            fx_ov.append("fade=t=in:st=0:d=0.25")
        elif clip.effect == "flash":
            fx_ov.append("fade=t=in:st=0:d=0.15:color=white")
        elif clip.effect == "spotlight":
            fx_ov.append("fade=t=in:st=0:d=0.15")
        fx_ov.append(f"setpts=PTS-STARTPTS+{clip.start:.3f}/TB")

        # Spotlight backdrop: làm tối nền xung quanh để nổi bật overlay / comment
        if getattr(clip, "dim_bg", False) or clip.effect == "spotlight":
            dim_lbl = f"dim_{i}"
            filters.append(
                f"[{last}]drawbox=x=0:y=0:w={W}:h={H}:color=black@0.65:t=fill:"
                f"enable='between(t,{clip.start:.3f},{clip.start + clip.dur:.3f})'[{dim_lbl}]"
            )
            last = dim_lbl

        filters.append(f"[{i}:v]{','.join(fx_ov)}[ov{i}]")
        out_lbl = f"o_ov{i}"
        filters.append(
            f"[{last}][ov{i}]overlay=eof_action=pass:"
            f"x='({W}*{clip.x_pct}/100)-(w/2)':y='({H}*{clip.y_pct}/100)-(h/2)':"
            f"enable='between(t,{clip.start:.3f},{clip.start + clip.dur:.3f})'[{out_lbl}]"
        )
        last = out_lbl

    # 3. Caption text overlay
    if concat is not None:
        cmd += ["-f", "concat", "-safe", "0", "-i", str(concat)]
        ci = n_in
        n_in += 1
        filters.append(f"[{last}][{ci}:v]overlay=eof_action=pass:format=auto[vout]")
        last = "vout"

    # 4. Audio voice
    has_voice = bool(proj.voice_file and (proj.dir / proj.voice_file).exists())
    if has_voice:
        cmd += ["-i", str(proj.dir / proj.voice_file)]
        ai = n_in
        n_in += 1

    if filters:
        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{last}]"]
    else:
        cmd += ["-map", "0:v"]
    if has_voice:
        cmd += ["-map", f"{ai}:a", "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", f"{dur:.3f}", "-pix_fmt", "yuv420p"]
    if encoder == "videotoolbox":
        cmd += ["-c:v", "h264_videotoolbox", "-b:v", "10M"]
    else:
        cmd += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "18"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def render_project(proj: Project, out: Path | None = None) -> Path:
    out = out or (proj.dir / "out" / f"{proj.name or proj.id}.mp4".replace(" ", "_"))
    out.parent.mkdir(parents=True, exist_ok=True)
    concat = render_caption_frames(proj) if proj.words else None
    try:
        _run(build_command(proj, out, concat, "videotoolbox"))
    except RuntimeError:
        _run(build_command(proj, out, concat, "libx264"))
    return out
