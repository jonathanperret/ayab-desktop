#!/usr/bin/env python3
"""Run the AYAB demo script while recording the screen with ffmpeg.

Usage: record_demo.py [--dark] OUTPUT.mp4 COMMAND [ARGS...]

COMMAND is run with AYAB_DEMO=1 (see src/main/python/main/ayab/demo.py).
The screen is captured with ffmpeg using the platform's native grabber
(x11grab on Linux, gdigrab on Windows, avfoundation on macOS).

With --dark, the system is switched to dark mode while the app runs:
- Linux: through the GTK3 platform theme and GTK_THEME=Adwaita:dark
- macOS: through System Events appearance preferences
- Windows: through the AppsUseLightTheme registry value, plus the
  darkmode=2 platform option and the Fusion style (needed by Qt 6.6)
The previous setting is restored afterwards.

On macOS, native menus are opened through System Events when the demo asks
for it (see MenuDriver), since Qt cannot open them itself.

ffmpeg is taken from $FFMPEG, then from PATH, then from the
`imageio-ffmpeg` package if installed.

Each demo step is captioned in the video (if Pillow is installed) and
becomes a chapter. A copy without captions is saved next to it, with a
"-plain" suffix (e.g. demo-plain.mp4). When the demo asks for it, the app
is relaunched once, still recording (see `after_relaunch` in demo.py).

Exits with 0 if the demo completed successfully, 1 otherwise.
"""

from __future__ import annotations
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
import threading
import time
from contextlib import contextmanager
from typing import Any, Iterator

FRAMERATE = "15"
TIMEOUT = 600


def find_ffmpeg() -> str:
    ffmpeg = os.environ.get("FFMPEG") or shutil.which("ffmpeg")
    if ffmpeg:
        return ffmpeg
    try:
        import imageio_ffmpeg  # type: ignore

        return str(imageio_ffmpeg.get_ffmpeg_exe())
    except ImportError:
        sys.exit("ffmpeg not found")


def macos_screen_device(ffmpeg: str) -> str:
    """Find the avfoundation index of the first screen."""
    listing = subprocess.run(
        [
            ffmpeg,
            "-hide_banner",
            "-f",
            "avfoundation",
            "-list_devices",
            "true",
            "-i",
            "",
        ],
        capture_output=True,
        text=True,
    ).stderr
    print(listing, flush=True)
    match = re.search(r"\[(\d+)\] Capture screen 0", listing)
    if not match:
        sys.exit("Could not find screen capture device")
    return match.group(1)


def input_args(ffmpeg: str) -> list[str]:
    if sys.platform.startswith("linux"):
        display = os.environ.get("DISPLAY", ":0")
        return [
            "-f",
            "x11grab",
            "-framerate",
            FRAMERATE,
            "-draw_mouse",
            "0",
            "-i",
            display,
        ]
    if sys.platform == "win32":
        return ["-f", "gdigrab", "-framerate", FRAMERATE, "-i", "desktop"]
    if sys.platform == "darwin":
        device = macos_screen_device(ffmpeg)
        return [
            "-f",
            "avfoundation",
            "-capture_cursor",
            "1",
            "-framerate",
            "30",
            "-pixel_format",
            "uyvy422",
            "-i",
            f"{device}:none",
        ]
    sys.exit(f"Unsupported platform {sys.platform}")


@contextmanager
def dark_mode(env: dict[str, str]) -> Iterator[None]:
    """Switch the system (or the app's environment) to dark mode."""
    if sys.platform.startswith("linux"):
        env["QT_QPA_PLATFORMTHEME"] = "gtk3"
        env["GTK_THEME"] = "Adwaita:dark"
        yield
    elif sys.platform == "darwin":
        # Writing the AppleInterfaceStyle default is not enough for newly
        # launched apps to pick it up, so go through System Events.
        previous = osascript(
            'tell application "System Events" to tell appearance preferences'
            " to get dark mode"
        )
        osascript(
            'tell application "System Events" to tell appearance preferences'
            " to set dark mode to true"
        )
        try:
            yield
        finally:
            osascript(
                'tell application "System Events" to tell appearance preferences'
                f" to set dark mode to {previous or 'false'}"
            )
    elif sys.platform == "win32":
        import winreg

        # Qt 6.6 only applies a dark palette with darkmode=2, and its default
        # windowsvista style ignores the palette, so use Fusion.
        env["QT_QPA_PLATFORM"] = "windows:darkmode=2"
        env["QT_STYLE_OVERRIDE"] = "Fusion"

        path = r"Software\Microsoft\Windows\CurrentVersion\Themes\Personalize"
        names = ["AppsUseLightTheme", "SystemUsesLightTheme"]
        with winreg.CreateKey(winreg.HKEY_CURRENT_USER, path) as key:
            previous = {}
            for name in names:
                try:
                    previous[name] = winreg.QueryValueEx(key, name)[0]
                except FileNotFoundError:
                    pass
                winreg.SetValueEx(key, name, 0, winreg.REG_DWORD, 0)
            try:
                yield
            finally:
                for name in names:
                    if name in previous:
                        winreg.SetValueEx(
                            key, name, 0, winreg.REG_DWORD, previous[name]
                        )
                    else:
                        winreg.DeleteValue(key, name)
    else:
        yield


def osascript(script: str) -> str | None:
    """Run an AppleScript snippet, returning its output or None on failure."""
    result = subprocess.run(
        ["osascript", "-e", script], capture_output=True, text=True, timeout=30
    )
    if result.returncode != 0:
        print(f"osascript failed: {result.stderr.strip()}", flush=True)
        return None
    return result.stdout.strip()


# Clicks "Allow" in system prompts (such as the macOS local network access
# prompt triggered by mDNS discovery) that would otherwise hide the app.
ALLOW_PROMPTS_SCRIPT = """
set clicked to {}
tell application "System Events"
    repeat with p in (every process)
        try
            repeat with w in (every window of p)
                if exists (button "Allow" of w) then
                    click button "Allow" of w
                    set end of clicked to (name of p as text)
                end if
            end repeat
        end try
    end repeat
end tell
return clicked as text
"""


class PromptDismisser(threading.Thread):
    def __init__(self) -> None:
        super().__init__(daemon=True)
        self.stopped = threading.Event()

    def run(self) -> None:
        while not self.stopped.wait(2):
            try:
                clicked = osascript(ALLOW_PROMPTS_SCRIPT)
            except subprocess.TimeoutExpired:
                continue
            if clicked is None:
                print("Giving up on dismissing system prompts", flush=True)
                return
            if clicked:
                print(f"Dismissed system prompt from {clicked}", flush=True)

    def stop(self) -> None:
        self.stopped.set()


def applescript_string(text: str) -> str:
    return '"' + text.replace("\\", "\\\\").replace('"', '\\"') + '"'


# Where Qt puts actions with these roles in the native macOS menus:
# the application menu (menu bar item 2, after the Apple menu)
APP_MENU_ITEMS = {
    "AboutRole": ["About"],
    "PreferencesRole": ["Settings", "Preferences"],
    "QuitRole": ["Quit"],
}


class MenuDriver(threading.Thread):
    """Shows native macOS menus being used, on behalf of the demo script.

    The demo writes `request.json` in `directory` with the app's pid, the
    menus leading to an action and its text. This opens the menu with System
    Events, highlights the item, closes the menu, then writes `response.json`
    with the path actually shown. The demo then triggers the action itself.
    """

    def __init__(self, directory: str) -> None:
        super().__init__(daemon=True)
        self.directory = directory
        self.stopped = threading.Event()

    def run(self) -> None:
        request = os.path.join(self.directory, "request.json")
        response = os.path.join(self.directory, "response.json")
        while not self.stopped.wait(0.1):
            if not os.path.exists(request):
                continue
            with open(request) as f:
                spec = json.load(f)
            os.remove(request)
            try:
                path = self.show(spec)
            except Exception as e:
                print(f"Could not show menu {spec}: {e}", flush=True)
                path = None
            with open(response + ".tmp", "w") as f:
                json.dump({"path": path}, f)
            os.replace(response + ".tmp", response)

    def show(self, spec: dict[str, Any]) -> list[str] | None:
        process = f"(first process whose unix id is {int(spec['pid'])})"
        prefixes = APP_MENU_ITEMS.get(spec["role"])
        if prefixes:
            menu_bar_item = "menu bar item 2 of menu bar 1 of p"
        else:
            prefixes = []
            title = applescript_string(spec["menus"][0])
            menu_bar_item = f"menu bar item {title} of menu bar 1 of p"
        tests = [f"n is {applescript_string(spec['item'])}"] + [
            f"n starts with {applescript_string(prefix)}" for prefix in prefixes
        ]
        # Clicking a menu bar item only returns once the menu is closed,
        # so do it in the background.
        opener = subprocess.Popen(
            [
                "osascript",
                "-e",
                f"""tell application "System Events"
                    set p to {process}
                    set frontmost of p to true
                    click {menu_bar_item}
                end tell""",
            ],
            stdout=subprocess.DEVNULL,
        )
        try:
            time.sleep(0.8)
            found = osascript(
                f"""tell application "System Events"
                    set p to {process}
                    set mbi to {menu_bar_item}
                    repeat with i in (menu items of menu 1 of mbi)
                        set n to name of i
                        if n is not missing value then
                            if {" or ".join(tests)} then
                                try
                                    set value of attribute "AXSelected" of i to true
                                end try
                                return (name of mbi) & tab & n
                            end if
                        end if
                    end repeat
                    return name of mbi
                end tell"""
            )
            time.sleep(0.8)
        finally:
            # close the menu
            osascript('tell application "System Events" to key code 53')
            try:
                opener.wait(timeout=10)
            except subprocess.TimeoutExpired:
                opener.kill()
        # without the item, keep the demo's own caption
        parts = found.split("\t") if found else []
        return parts if len(parts) == 2 else None

    def stop(self) -> None:
        self.stopped.set()


@contextmanager
def light_mode(env: dict[str, str]) -> Iterator[None]:
    yield


class Recorder:
    """Runs ffmpeg, and finds the wall-clock time of the first frame."""

    def __init__(self, ffmpeg: str, output: str) -> None:
        args = input_args(ffmpeg)
        # timestamp captured frames with the wall clock, so that the start
        # time ffmpeg reports for the input tells when the video starts
        i = args.index("-i")
        args[i:i] = ["-use_wallclock_as_timestamps", "1"]
        self.process = subprocess.Popen(
            [ffmpeg, "-hide_banner", "-nostats", "-loglevel", "info", "-y"]
            + args
            + [
                "-r",
                FRAMERATE,
                # scale down HiDPI screens, and ensure even dimensions for x264
                "-vf",
                "scale='min(1920,iw)':-2",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-pix_fmt",
                "yuv420p",
                output,
            ],
            stdin=subprocess.PIPE,
            stderr=subprocess.PIPE,
        )
        self.start: float | None = None
        self.reader = threading.Thread(target=self.read_log, daemon=True)
        self.reader.start()

    def read_log(self) -> None:
        assert self.process.stderr
        for raw in self.process.stderr:
            line = raw.decode(errors="replace").rstrip()
            match = re.search(r"Duration: N/A, start: ([0-9.]+)", line)
            if match and self.start is None:
                self.start = float(match.group(1))
            elif re.search(r"error|warning|fail", line, re.IGNORECASE):
                print(f"ffmpeg: {line}", flush=True)

    def stop(self) -> None:
        """Ask ffmpeg to stop gracefully, so that the output is finalized."""
        assert self.process.stdin
        try:
            self.process.stdin.write(b"q")
            self.process.stdin.close()
            self.process.wait(timeout=60)
        except (OSError, subprocess.TimeoutExpired):
            self.process.kill()
            self.process.wait()
        self.reader.join(timeout=5)


def video_info(ffmpeg: str, path: str) -> tuple[float, int, int] | None:
    """Duration, width and height of a video."""
    info = subprocess.run(
        [ffmpeg, "-hide_banner", "-i", path], capture_output=True, text=True
    ).stderr
    duration = re.search(r"Duration: (\d+):(\d+):([0-9.]+)", info)
    size = re.search(r"Video: .*?, (\d{2,5})x(\d{2,5})", info)
    if not duration or not size:
        return None
    h, m, sec = duration.groups()
    seconds = int(h) * 3600 + int(m) * 60 + float(sec)
    return seconds, int(size.group(1)), int(size.group(2))


def ffmetadata_escape(text: str) -> str:
    return re.sub(r"([=;#\\\n])", r"\\\1", text)


def caption_font(size: int) -> Any:
    """A bold font covering the characters used in captions (›, –, é...)."""
    from PIL import ImageFont

    for name in [
        "DejaVuSans-Bold.ttf",  # Linux
        "Arial Bold.ttf",  # macOS
        "arialbd.ttf",  # Windows
    ]:
        try:
            return ImageFont.truetype(name, size)
        except OSError:
            pass
    try:
        # Pillow's own font, which lacks some characters
        return ImageFont.load_default(size=size)  # type: ignore # Pillow >= 10.1
    except TypeError:
        return ImageFont.load_default()


def make_caption(text: str, height: int, path: str) -> None:
    """Draw a caption image, scaled for a video `height` pixels high."""
    from PIL import Image, ImageDraw

    font_size = max(14, height // 34)
    font = caption_font(font_size)
    pad_x, pad_y, border = font_size, font_size // 2, max(2, font_size // 6)
    left, top, right, bottom = font.getbbox(text)
    width = right - left + 2 * (pad_x + border)
    box_height = bottom - top + 2 * (pad_y + border)
    # draw at 4x and scale down, for smooth rounded corners
    k = 4
    image = Image.new("RGBA", (width * k, box_height * k), (0, 0, 0, 0))
    draw = ImageDraw.Draw(image)
    draw.rounded_rectangle(
        (0, 0, width * k - 1, box_height * k - 1),
        radius=font_size // 2 * k,
        fill=(32, 32, 32, 235),
        outline=(240, 176, 0, 255),
        width=border * k,
    )
    image = image.resize((width, box_height), Image.Resampling.LANCZOS)
    draw = ImageDraw.Draw(image)
    draw.text(
        (pad_x + border - left, pad_y + border - top), text, font=font, fill="white"
    )
    image.save(path)


def finish_video(ffmpeg: str, output: str, start: float, steps_file: str) -> None:
    """Caption each demo step in the video, and add a chapter for it."""
    try:
        with open(steps_file, encoding="utf-8") as f:
            steps = [json.loads(line) for line in f if line.strip()]
    except FileNotFoundError:
        steps = []
    info = video_info(ffmpeg, output)
    if not steps or info is None:
        print("No steps or video information: video left as is", flush=True)
        return
    duration, _, height = info
    # (start, title, caption) of each chapter
    chapters: list[tuple[float, str, bool]] = [(0.0, "Starting AYAB", False)]
    for step in steps:
        if step.get("retitle"):
            begin, _, caption = chapters[-1]
            chapters[-1] = (begin, step["step"], caption)
        else:
            chapters.append((max(0.0, step["t"] - start), step["step"], True))
    spans = []
    for i, (begin, title, caption) in enumerate(chapters):
        end = chapters[i + 1][0] if i + 1 < len(chapters) else duration
        if end > begin:
            spans.append((begin, end, title, caption))

    lines = [";FFMETADATA1"]
    for begin, end, title, _ in spans:
        lines += [
            "[CHAPTER]",
            "TIMEBASE=1/1000",
            f"START={int(begin * 1000)}",
            f"END={int(end * 1000)}",
            f"title={ffmetadata_escape(title)}",
        ]
    directory = os.path.dirname(steps_file)
    metadata = os.path.join(directory, "chapters.ffmetadata")
    with open(metadata, "w", encoding="utf-8") as f:
        f.write("\n".join(lines) + "\n")

    inputs = ["-i", output, "-i", metadata]
    graph: list[str] = []
    try:
        captions = [(b, e, t) for b, e, t, caption in spans if caption]
        last = "0:v"
        for i, (begin, end, title) in enumerate(captions):
            image = os.path.join(directory, f"caption{i}.png")
            make_caption(title, height, image)
            inputs += ["-i", image]
            graph.append(
                f"[{last}][{i + 2}:v]overlay=x=(W-w)/2:y=H-h-H/8"
                f":enable='between(t,{begin:.3f},{end:.3f})'[v{i}]"
            )
            last = f"v{i}"
    except ImportError:
        print("Pillow is not installed: no captions", flush=True)
        graph = []
    chapters_args = ["-map_metadata", "1", "-map_chapters", "1"]
    # the video with chapters only, e.g. for utils/montage_demo.py
    plain = plain_path(output)
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-y", "-i", output, "-i", metadata]
        + chapters_args
        + ["-map", "0", "-c", "copy", plain]
    )
    if result.returncode != 0:
        print("Could not add chapters", flush=True)
        return
    if not graph:
        os.replace(plain, output)
        print(f"Added {len(spans)} chapters", flush=True)
        return
    captioned = output + ".captioned.mp4"
    result = subprocess.run(
        [ffmpeg, "-v", "error", "-y"]
        + inputs
        + chapters_args
        + ["-filter_complex", ";".join(graph), "-map", f"[{last}]"]
        + ["-c:v", "libx264", "-preset", "veryfast", "-pix_fmt", "yuv420p"]
        + [captioned]
    )
    if result.returncode == 0:
        os.replace(captioned, output)
        print(
            f"Added {len(spans)} chapters, {len(graph)} captions"
            f" (without captions: {os.path.basename(plain)})",
            flush=True,
        )
    else:
        print("Could not add captions", flush=True)
        os.replace(plain, output)


def plain_path(output: str) -> str:
    """Where the video without captions is saved."""
    base, ext = os.path.splitext(output)
    return f"{base}-plain{ext}"


def run_app(command: list[str], env: dict[str, str]) -> int:
    try:
        return subprocess.run(command, env=env, timeout=TIMEOUT).returncode
    except subprocess.TimeoutExpired:
        print("App timed out", flush=True)
        return -1


def read_result(path: str) -> str:
    try:
        with open(path) as f:
            result = f.read().strip()
        os.remove(path)
        return result
    except FileNotFoundError:
        return "missing"


def main() -> int:
    args = sys.argv[1:]
    dark = "--dark" in args
    if dark:
        args.remove("--dark")
    if len(args) < 2:
        sys.exit(__doc__)
    output, command = args[0], args[1:]

    ffmpeg = find_ffmpeg()
    recorder = Recorder(ffmpeg, output)
    # give the recorder a moment to start up
    time.sleep(2)
    if recorder.process.poll() is not None:
        print(f"ffmpeg exited early with code {recorder.process.returncode}")
        return 1

    with tempfile.TemporaryDirectory() as tmp:
        result_file = os.path.join(tmp, "result")
        steps_file = os.path.join(tmp, "steps.jsonl")
        env = dict(
            os.environ,
            AYAB_DEMO="1",
            AYAB_DEMO_RESULT=result_file,
            AYAB_DEMO_STEPS=steps_file,
        )
        mode = "dark" if dark else "light"
        print(f"Running {command} in {mode} mode", flush=True)
        dismisser = PromptDismisser() if sys.platform == "darwin" else None
        menu_driver = None
        if sys.platform == "darwin":
            env["AYAB_DEMO_MENU_DIR"] = tmp
            menu_driver = MenuDriver(tmp)
            menu_driver.start()
        with (dark_mode if dark else light_mode)(env):
            if dismisser:
                dismisser.start()
            launches = 0
            while True:
                launches += 1
                exit_code = run_app(command, env)
                result = read_result(result_file)
                # The demo can ask to be relaunched (once), passing along
                # the language to restore.
                if result.startswith("relaunch") and launches == 1:
                    print("Relaunching the app", flush=True)
                    env["AYAB_DEMO_RELAUNCH"] = result.partition("\n")[2].strip()
                    continue
                break
            if dismisser:
                dismisser.stop()
            if menu_driver:
                menu_driver.stop()

        recorder.stop()
        if recorder.start is None:
            print("Video start time unknown, no chapters added", flush=True)
        else:
            finish_video(ffmpeg, output, recorder.start, steps_file)

    print(f"App exit code: {exit_code}, demo result: {result}", flush=True)
    return 0 if result == "success" else 1


if __name__ == "__main__":
    sys.exit(main())
