#!/usr/bin/env python3
"""CLI cho agent / batch.   python -m studio.cli.studio <lệnh>

  new "Tên"                      tạo project, in id
  script <id> "text" | -f file   đặt script
  voice <id> [--voice V] [--style S] [--speed X]   script -> giọng + mốc từng từ
  add-media <id> <file>          copy vào media/
  clip <id> <src> <start> <dur> [--in N] [--fit cover|contain_blur]
  render <id>                    xuất mp4
  show <id>                      in project.json
"""
from __future__ import annotations

import argparse
import shutil
import sys
from pathlib import Path

from ..core.project import Clip, Project, list_projects


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="studio")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("new"); p.add_argument("name")
    sub.add_parser("list")
    p = sub.add_parser("script"); p.add_argument("id"); p.add_argument("text", nargs="?"); p.add_argument("-f", "--file")
    p = sub.add_parser("voice"); p.add_argument("id")
    p.add_argument("--voice"); p.add_argument("--style"); p.add_argument("--speed", type=float)
    p = sub.add_parser("add-media"); p.add_argument("id"); p.add_argument("file")
    p = sub.add_parser("clip"); p.add_argument("id"); p.add_argument("src")
    p.add_argument("start", type=float); p.add_argument("dur", type=float)
    p.add_argument("--in", dest="in_point", type=float, default=0.0)
    p.add_argument("--fit", default="cover", choices=["cover", "contain_blur"])
    p = sub.add_parser("auto-broll"); p.add_argument("id")
    p = sub.add_parser("render"); p.add_argument("id")
    p = sub.add_parser("show"); p.add_argument("id")

    a = ap.parse_args(argv)

    if a.cmd == "new":
        print(Project.create(a.name).id)
    elif a.cmd == "list":
        for x in list_projects():
            print(x["id"], x["name"])
    elif a.cmd == "script":
        proj = Project.load(a.id)
        proj.script = Path(a.file).read_text(encoding="utf-8") if a.file else (a.text or "")
        proj.save()
        print("ok")
    elif a.cmd == "voice":
        from ..core.workflows.voiceover import build_voiceover

        proj = Project.load(a.id)
        if a.voice: proj.voice.voice = a.voice
        if a.style: proj.voice.style = a.style
        if a.speed: proj.voice.speed = a.speed
        proj = build_voiceover(proj)
        print(f"voice ok · {len(proj.words)} từ · {proj.duration:.1f}s")
    elif a.cmd == "add-media":
        proj = Project.load(a.id)
        proj.media_dir.mkdir(parents=True, exist_ok=True)
        dest = proj.media_dir / Path(a.file).name
        shutil.copy2(a.file, dest)
        print(f"media/{dest.name}")
    elif a.cmd == "clip":
        proj = Project.load(a.id)
        proj.clips.append(Clip(src=a.src, start=a.start, dur=a.dur, in_point=a.in_point, fit=a.fit))
        proj.save()
        print("ok")
    elif a.cmd == "auto-broll":
        from ..core.workflows.voiceover import auto_broll

        proj = auto_broll(Project.load(a.id))
        print(f"auto-broll ok · {len(proj.clips)} clips")
    elif a.cmd == "render":
        from ..render.compiler import render_project

        print(render_project(Project.load(a.id)))
    elif a.cmd == "show":
        print(Project.load(a.id).model_dump_json(indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
