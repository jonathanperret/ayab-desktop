#!/usr/bin/env python3
"""Combine demo videos into a single montage, synchronized on their chapters.

Usage: montage_demo.py VIDEO_DIR OUTPUT.mp4

VIDEO_DIR holds videos recorded by utils/record_demo.py, named
[demo-]{linux,macos,windows}-{light,dark}[-plain].mp4 (any subset; the
"-plain" ones, without captions, are preferred). They are laid out in a grid,
one row per platform, light on the left and dark on the right, with a single
caption for the current step below.

record_demo.py adds a chapter per demo step. Each video is cut at every
chapter, and each segment is padded (holding its last frame) to the longest
duration of that segment across the videos, so that all of them show the
same step at the same time. The montage gets the chapters too.

Requires ffmpeg and ffprobe on PATH, and Pillow (for the labels).
"""

from __future__ import annotations
import json
import os
import subprocess
import sys
import tempfile
from typing import Any

from PIL import Image, ImageDraw

from record_demo import caption_font, make_caption

TILE_W, TILE_H = 960, 600
# height of the band below the videos, for the caption
CAPTION_BAND = 110
FRAMERATE = 15
PLATFORMS = [("linux", "Linux"), ("macos", "macOS"), ("windows", "Windows")]
MODES = ["light", "dark"]


def find_videos(directory: str) -> list[tuple[str, str]]:
    """(path, label) of the videos found, in grid order."""
    videos = []
    for platform, name in PLATFORMS:
        for mode in MODES:
            candidates = [
                os.path.join(directory, f"{prefix}{platform}-{mode}{suffix}.mp4")
                for suffix in ["-plain", ""]
                for prefix in ["demo-", ""]
            ]
            found = [path for path in candidates if os.path.exists(path)]
            if found:
                videos.append((found[0], f"{name} · {mode}"))
    return videos


def probe(path: str) -> dict[str, Any]:
    result = subprocess.run(
        ["ffprobe", "-v", "error", "-show_chapters", "-show_format"]
        + ["-of", "json", path],
        capture_output=True,
        text=True,
        check=True,
    )
    info: dict[str, Any] = json.loads(result.stdout)
    return info


def make_label(text: str, path: str) -> None:
    font = caption_font(30)
    width = int(font.getlength(text)) + 32
    image = Image.new("RGBA", (width, 48), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, width - 1, 47),
        10,
        fill=(32, 32, 32, 220),
        outline=(240, 176, 0, 255),
        width=3,
    )
    draw.text((16, 8), text, font=font, fill="white")
    image.save(path)


def ffmetadata_escape(text: str) -> str:
    for c in "\\=;#\n":
        text = text.replace(c, "\\" + c)
    return text


def main() -> int:
    if len(sys.argv) != 3:
        sys.exit(__doc__)
    directory, output = sys.argv[1], sys.argv[2]

    videos = find_videos(directory)
    if not videos:
        sys.exit(f"No demo videos found in {directory}")
    infos = [probe(path) for path, _ in videos]
    chapters = [
        [(float(c["start_time"]), c["tags"].get("title", "")) for c in info["chapters"]]
        for info in infos
    ]
    for (path, _), video_chapters in zip(videos, chapters):
        print(f"{os.path.basename(path)}: {len(video_chapters)} chapters")
        if not video_chapters:
            sys.exit(f"{path} has no chapters")
    n = min(len(c) for c in chapters)
    if len({len(c) for c in chapters}) != 1:
        print(f"Warning: chapter counts differ, synchronizing the first {n}")

    # cut points: the chapter starts, then the end of the video
    cuts = [
        [start for start, _ in video_chapters[:n]] + [float(info["format"]["duration"])]
        for video_chapters, info in zip(chapters, infos)
    ]
    targets = [max(c[i + 1] - c[i] for c in cuts) for i in range(n)]

    with tempfile.TemporaryDirectory() as tmp:
        labels = []
        for i, (_, text) in enumerate(videos):
            labels.append(os.path.join(tmp, f"label{i}.png"))
            make_label(text, labels[-1])

        scale = (
            f"scale={TILE_W}:{TILE_H}:force_original_aspect_ratio=decrease,"
            f"pad={TILE_W}:{TILE_H}:(ow-iw)/2:(oh-ih)/2:color=black,fps={FRAMERATE}"
        )
        k = len(videos)
        graph = []
        for v in range(k):
            c = cuts[v]
            graph.append(
                f"[{v}:v]{scale},split={n}" + "".join(f"[s{v}_{i}]" for i in range(n))
            )
            for i in range(n):
                pad = targets[i] - (c[i + 1] - c[i])
                graph.append(
                    f"[s{v}_{i}]trim=start={c[i]:.3f}:end={c[i + 1]:.3f},"
                    f"setpts=PTS-STARTPTS,"
                    f"tpad=stop_mode=clone:stop_duration={pad:.3f}[t{v}_{i}]"
                )
            graph.append(
                "".join(f"[t{v}_{i}]" for i in range(n)) + f"concat=n={n}:v=1:a=0[c{v}]"
            )
            graph.append(f"[c{v}][{k + v}:v]overlay=W-w-16:H-h-16[b{v}]")
        if k == 1:
            graph.append("[b0]null[grid]")
        else:
            layout = "|".join(
                f"{(v % 2) * TILE_W}_{(v // 2) * TILE_H}" for v in range(k)
            )
            graph.append(
                "".join(f"[b{v}]" for v in range(k))
                + f"xstack=inputs={k}:layout={layout}:fill=black[grid]"
            )
        graph.append(f"[grid]pad=iw:ih+{CAPTION_BAND}:0:0:color=black[c]")

        # Chapters and captions, titled after the first video's chapters, plus
        # any different titles (e.g. macOS has About in the application menu).
        # The first chapter (the app starting) is not captioned.
        metadata = [";FFMETADATA1"]
        captions = []
        last = "c"
        t = 0.0
        for i in range(n):
            titles: list[str] = []
            for video_chapters in chapters:
                if video_chapters[i][1] not in titles:
                    titles.append(video_chapters[i][1])
            title = " / ".join(titles)
            metadata += [
                "[CHAPTER]",
                "TIMEBASE=1/1000",
                f"START={int(t * 1000)}",
                f"END={int((t + targets[i]) * 1000)}",
                f"title={ffmetadata_escape(title)}",
            ]
            if i > 0:
                captions.append(os.path.join(tmp, f"caption{i}.png"))
                # sized for a font about 40% of the band's height
                make_caption(title, CAPTION_BAND * 14, captions[-1])
                index = 2 * k + len(captions)
                graph.append(
                    f"[{last}][{index}:v]overlay=x=(W-w)/2"
                    f":y=H-{CAPTION_BAND}+({CAPTION_BAND}-h)/2"
                    f":enable='between(t,{t:.3f},{t + targets[i]:.3f})'[cap{i}]"
                )
                last = f"cap{i}"
            t += targets[i]
        metadata_file = os.path.join(tmp, "chapters.txt")
        with open(metadata_file, "w", encoding="utf-8") as f:
            f.write("\n".join(metadata) + "\n")

        command = ["ffmpeg", "-hide_banner", "-loglevel", "error", "-y"]
        for path, _ in videos:
            command += ["-i", path]
        for label in labels:
            command += ["-i", label]
        command += ["-i", metadata_file]
        for caption in captions:
            command += ["-i", caption]
        command += ["-filter_complex", ";".join(graph), "-map", f"[{last}]"]
        command += ["-map_chapters", str(2 * k)]
        command += ["-c:v", "libx264", "-preset", "veryfast", "-crf", "23"]
        command += ["-pix_fmt", "yuv420p", output]
        subprocess.run(command, check=True)

    print(f"Wrote {output}: {k} videos, {n} chapters, {sum(targets):.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
