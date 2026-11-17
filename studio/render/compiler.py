"""Compile project.json -> ffmpeg -> mp4."""
from __future__ import annotations

import re
import subprocess
from pathlib import Path

from ..core.project import Project
from .captions import render_caption_frames

IMAGE_EXTS = {".png", ".jpg", ".jpeg", ".webp"}


def _run(cmd: list[str]) -> None:
    proc = subprocess.run(cmd, capture_output=True, text=True)
    if proc.returncode != 0:
        raise RuntimeError(f"ffmpeg lỗi:\n{proc.stderr[-1200:]}")


def build_command(
    proj: Project,
    out: Path,
    concat: Path | None,
    encoder: str,
    quality: str = "1080p",
    eco_mode: bool = True,
) -> list[str]:
    # Độ phân giải linh hoạt: 480p (nhanh mát), 720p (chuẩn TikTok/Shorts), 1080p (Full HD)
    if quality == "480p":
        W, H = 480, 854
        target_bitrate = "1800k"
    elif quality == "720p":
        W, H = 720, 1280
        target_bitrate = "3500k"
    else:  # 1080p mặc định
        W, H = proj.width, proj.height
        target_bitrate = "7000k"

    fps = proj.fps
    dur = max(proj.duration, 0.5) + 0.3
    cmd = [
        "ffmpeg", "-y",
    ]
    # Giới hạn luồng (Eco mode) để CPU không bao giờ bị quá tải 100%, máy luôn mát mẻ
    if eco_mode:
        cmd += ["-threads", "3"]

    cmd += [
        "-f", "lavfi", "-i",
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
        speed = max(0.1, float(getattr(clip, "speed", 1.0) or 1.0))
        if src.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop", "1", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        else:
            src_dur = clip.dur * speed
            cmd += ["-ss", f"{clip.in_point:.3f}", "-t", f"{src_dur:.3f}", "-i", str(src)]
        i = n_in
        n_in += 1

        fx = []
        if clip.fit == "contain_blur":
            # Tối ưu hóa cực mạnh: Thu nhỏ nền trước khi blur -> giảm 95% tải CPU, render cực mát!
            small_w, small_h = max(W // 4, 120), max(H // 4, 210)
            base_f = (
                f"[{i}:v]split[a{i}][b{i}];"
                f"[a{i}]scale={small_w}:{small_h}:force_original_aspect_ratio=increase,crop={small_w}:{small_h},boxblur=10:2,scale={W}:{H}[bg{i}];"
                f"[b{i}]scale={W}:{H}:force_original_aspect_ratio=decrease[fg{i}];"
                f"[bg{i}][fg{i}]overlay=(W-w)/2:(H-h)/2,fps={fps}[vraw{i}]"
            )
            filters.append(base_f)
            v_in = f"vraw{i}"
        else:
            # Reframe & Crop thông minh: Cho phép chọn góc cắt (crop_x, crop_y, crop_scale)
            cx = max(0.0, min(100.0, getattr(clip, "crop_x", 50.0) or 50.0)) / 100.0
            cy = max(0.0, min(100.0, getattr(clip, "crop_y", 50.0) or 50.0)) / 100.0
            c_scale = max(100.0, min(300.0, getattr(clip, "crop_scale", 100.0) or 100.0)) / 100.0

            if c_scale > 1.0:
                target_sw = int(W * c_scale)
                target_sh = int(H * c_scale)
                scale_part = f"scale={target_sw}:{target_sh}:force_original_aspect_ratio=increase"
            else:
                scale_part = f"scale={W}:{H}:force_original_aspect_ratio=increase"

            crop_part = f"crop={W}:{H}:(in_w-out_w)*{cx:.4f}:(in_h-out_h)*{cy:.4f}"
            filters.append(f"[{i}:v]{scale_part},{crop_part},fps={fps}[vraw{i}]")
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

        if src.suffix.lower() not in IMAGE_EXTS and abs(speed - 1.0) > 0.01:
            fx.append(f"setpts=(PTS-STARTPTS)/{speed:.4f}+{clip.start:.3f}/TB")
        else:
            fx.append(f"setpts=PTS-STARTPTS+{clip.start:.3f}/TB")
        filters.append(f"[{v_in}]{','.join(fx)}[v{i}]")

        out_lbl = f"o{i}"
        filters.append(
            f"[{last}][v{i}]overlay=eof_action=pass:"
            f"enable='between(t,{clip.start:.3f},{clip.start + clip.dur:.3f})'[{out_lbl}]"
        )
        last = out_lbl

    # 1.5. Chữ khổng lồ sau lưng (Cinematic Depth Text)
    bg_text = getattr(proj, "bg_text", "") or ""
    if bg_text.strip():
        safe_txt = bg_text.replace("'", "").replace(":", "").upper()
        bg_size = getattr(proj, "bg_text_size", 240) or 240
        bg_col = getattr(proj, "bg_text_color", "#FFFFFF1A") or "#FFFFFF1A"
        bg_y = getattr(proj, "bg_text_y_pct", 40.0) or 40.0
        h_col = bg_col.lstrip("#")
        alpha_f = 0.12
        if len(h_col) == 8:
            alpha_f = int(h_col[6:8], 16) / 255.0
            hex_c = h_col[:6]
        else:
            hex_c = h_col[:6] if len(h_col) >= 6 else "FFFFFF"
        font_path = "/System/Library/Fonts/Supplemental/Impact.ttf"
        font_param = f":fontfile='{font_path}'" if Path(font_path).exists() else ""
        txt_filter = (
            f"[{last}]drawtext=text='{safe_txt}'{font_param}:fontsize={bg_size}:"
            f"fontcolor={hex_c}@{alpha_f:.2f}:x=(w-text_w)/2:y=(h-text_h)*{bg_y:.2f}/100[v_bg_text]"
        )
        filters.append(txt_filter)
        last = "v_bg_text"

    # 2. Overlay / Icon / Sticker track (z_order nhỏ vẽ trước, z_order lớn vẽ sau -> đè lên trên)
    for clip in sorted(overlay_clips, key=lambda c: (getattr(c, "z_order", 0) or 0, c.start)):
        src = proj.dir / clip.src
        if not src.exists():
            continue
        speed_ov = max(0.1, float(getattr(clip, "speed", 1.0) or 1.0))
        if src.suffix.lower() in IMAGE_EXTS:
            cmd += ["-loop", "1", "-t", f"{clip.dur:.3f}", "-i", str(src)]
        else:
            src_dur = clip.dur * speed_ov
            cmd += ["-ss", f"{clip.in_point:.3f}", "-t", f"{src_dur:.3f}", "-i", str(src)]
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
        if src.suffix.lower() not in IMAGE_EXTS and abs(speed_ov - 1.0) > 0.01:
            fx_ov.append(f"setpts=(PTS-STARTPTS)/{speed_ov:.4f}+{clip.start:.3f}/TB")
        else:
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
        if (W, H) != (proj.width, proj.height):
            filters.append(f"[{ci}:v]scale={W}:{H}[cap_scaled]")
            filters.append(f"[{last}][cap_scaled]overlay=eof_action=pass:format=auto[vout]")
        else:
            filters.append(f"[{last}][{ci}:v]overlay=eof_action=pass:format=auto[vout]")
        last = "vout"

    # 4. Audio: Voice, SFX & BGM
    has_voice = bool(proj.voice_file and (proj.dir / proj.voice_file).exists())
    has_bgm = bool(proj.bgm_file and (proj.dir / proj.bgm_file).exists())
    sfx_clips = getattr(proj, "sfx_clips", []) or []
    out_a = None

    voice_lbl = None
    if has_voice:
        cmd += ["-i", str(proj.dir / proj.voice_file)]
        vi = n_in
        n_in += 1
        voice_offset = getattr(proj.voice, "offset", 0.0) or 0.0
        if voice_offset > 0:
            d_ms = int(voice_offset * 1000)
            filters.append(f"[{vi}:a]adelay={d_ms}|{d_ms}[v_a]")
            voice_lbl = "v_a"
        else:
            voice_lbl = f"{vi}:a"

    # Âm thanh hiệu ứng SFX (Whoosh, Pop, Ding, Glitch...)
    sfx_labels = []
    for sfx in sfx_clips:
        rel_src = sfx.src.lstrip("/")
        sfx_path = proj.dir / rel_src
        if not sfx_path.exists():
            sfx_path = Path(__file__).resolve().parents[1] / rel_src.replace("studio-assets/", "assets/")
        if not sfx_path.exists():
            sfx_path = Path(__file__).resolve().parents[1] / "assets" / "sfx" / Path(sfx.src).name
            cmd += ["-i", str(sfx_path)]
            si = n_in
            n_in += 1
            s_ms = max(0, int(round(sfx.start * 1000)))
            vol = getattr(sfx, "volume", 0.8) or 0.8
            filters.append(f"[{si}:a]volume={vol:.2f},adelay={s_ms}|{s_ms}[sfx_{si}]")
            sfx_labels.append(f"sfx_{si}")

    bgm_lbl = None
    if has_bgm:
        cmd += ["-stream_loop", "-1", "-i", str(proj.dir / proj.bgm_file)]
        bi = n_in
        n_in += 1
        bgm_offset = getattr(proj, "bgm_offset", 0.0) or 0.0
        bgm_vol = getattr(proj, "bgm_volume", 0.25) or 0.25
        if bgm_offset > 0:
            b_ms = int(bgm_offset * 1000)
            filters.append(f"[{bi}:a]volume={bgm_vol:.2f},adelay={b_ms}|{b_ms}[bgm_a]")
            bgm_lbl = "bgm_a"
        else:
            filters.append(f"[{bi}:a]volume={bgm_vol:.2f}[bgm_a]")
            bgm_lbl = "bgm_a"

    # Hòa âm tất cả các luồng âm thanh
    all_mix = []
    if voice_lbl:
        all_mix.append(f"[{voice_lbl}]")
    for sl in sfx_labels:
        all_mix.append(f"[{sl}]")
    if bgm_lbl:
        all_mix.append(f"[{bgm_lbl}]")

    if len(all_mix) > 1:
        filters.append(f"{''.join(all_mix)}amix=inputs={len(all_mix)}:duration=longest:normalize=0[aout]")
        out_a = "[aout]"
    elif len(all_mix) == 1:
        out_a = all_mix[0]

    if filters:
        cmd += ["-filter_complex", ";".join(filters), "-map", f"[{last}]"]
    else:
        cmd += ["-map", "0:v"]
    if out_a:
        cmd += ["-map", out_a, "-c:a", "aac", "-b:a", "192k"]
    cmd += ["-t", f"{dur:.3f}", "-pix_fmt", "yuv420p"]
    if encoder == "videotoolbox":
        cmd += ["-c:v", "h264_videotoolbox", "-b:v", target_bitrate, "-realtime", "0"]
    else:
        preset = "superfast" if eco_mode else "veryfast"
        cmd += ["-c:v", "libx264", "-preset", preset, "-crf", "20"]
    cmd += ["-movflags", "+faststart", str(out)]
    return cmd


def render_project(
    proj: Project,
    out: Path | None = None,
    quality: str = "1080p",
    eco_mode: bool = True,
) -> Path:
    default_name = out.name if out else f"{proj.name or proj.id}_{quality}.mp4".replace(" ", "_")
    default_out = proj.dir / "out" / default_name
    target_out = out or default_out
    target_out.parent.mkdir(parents=True, exist_ok=True)
    concat = render_caption_frames(proj) if proj.words else None
    try:
        _run(build_command(proj, target_out, concat, "videotoolbox", quality, eco_mode))
    except RuntimeError:
        _run(build_command(proj, target_out, concat, "libx264", quality, eco_mode))

    # Đảm bảo luôn có 1 bản trong project out/ để web có thể phát preview / tải về
    if target_out.resolve() != default_out.resolve():
        default_out.parent.mkdir(parents=True, exist_ok=True)
        import shutil
        shutil.copy2(target_out, default_out)

    return target_out


def crop_clip_source(
    proj: Project,
    src_rel: str,
    crop_x: float = 50.0,
    crop_y: float = 50.0,
    crop_scale: float = 100.0,
    name: str | None = None,
) -> str:
    """Cắt trực tiếp một file nguồn theo vùng crop (9:16) thành 1 file media mới trong project."""
    src_file = proj.dir / src_rel
    if not src_file.exists():
        raise FileNotFoundError(f"Không tìm thấy file nguồn: {src_rel}")

    safe_name = name or f"crop_{Path(src_rel).stem}"
    safe_name = re.sub(r"[^\w\-]", "_", safe_name)
    ext = src_file.suffix.lower()
    dest_name = f"media/{safe_name}_9x16{ext if ext in IMAGE_EXTS else '.mp4'}"
    dest_file = proj.dir / dest_name
    dest_file.parent.mkdir(parents=True, exist_ok=True)

    W, H = proj.width, proj.height
    cx = max(0.0, min(100.0, crop_x)) / 100.0
    cy = max(0.0, min(100.0, crop_y)) / 100.0
    c_scale = max(100.0, min(300.0, crop_scale)) / 100.0

    if c_scale > 1.0:
        target_sw = int(W * c_scale)
        target_sh = int(H * c_scale)
        scale_part = f"scale={target_sw}:{target_sh}:force_original_aspect_ratio=increase"
    else:
        scale_part = f"scale={W}:{H}:force_original_aspect_ratio=increase"

    crop_part = f"crop={W}:{H}:(in_w-out_w)*{cx:.4f}:(in_h-out_h)*{cy:.4f}"

    if ext in IMAGE_EXTS:
        cmd = [
            "ffmpeg", "-y", "-i", str(src_file),
            "-vf", f"{scale_part},{crop_part}",
            str(dest_file),
        ]
    else:
        cmd = [
            "ffmpeg", "-y", "-i", str(src_file),
            "-vf", f"{scale_part},{crop_part}",
            "-c:v", "h264_videotoolbox", "-b:v", "6000k", "-c:a", "copy",
            "-movflags", "+faststart", str(dest_file),
        ]
    try:
        _run(cmd)
    except RuntimeError:
        if ext not in IMAGE_EXTS:
            cmd = [
                "ffmpeg", "-y", "-i", str(src_file),
                "-vf", f"{scale_part},{crop_part}",
                "-c:v", "libx264", "-preset", "veryfast", "-crf", "18", "-c:a", "copy",
                "-movflags", "+faststart", str(dest_file),
            ]
            _run(cmd)

    return dest_name
