# Running AYAB in Docker

These scripts run AYAB in a Linux container, either natively on Linux or as the
Windows build under Wine, and open a VNC viewer on it: TigerVNC if installed
(`brew install --cask tigervnc-viewer`), otherwise macOS Screen Sharing. Run
them from anywhere. They all use the same image, built from
`docker/Dockerfile` on each launch (cached after the first time). Source runs
mount the checkout, so changes are picked up on the next launch.

| Command                                                  | Runs                                          |
| -------------------------------------------------------- | --------------------------------------------- |
| `linux-build/run-appimage.sh AYAB-x.y.z-x86_64.AppImage` | a Linux release AppImage                      |
| `linux-build/run-source.sh`                              | this checkout on Linux (`fbs run`)            |
| `windows-build/run-release.sh AYAB-x.y.z.exe`            | a Windows release installer, under Wine       |
| `windows-build/run-source.sh`                            | this checkout with Windows Python, under Wine |

The scripts follow the app's log; press Ctrl-C to stop the container.

Environment variables:

- `DARK_MODE=1`: dark mode (GTK's dark theme on Linux; the Windows dark-mode
  preference and Qt's Fusion style under Wine). Light mode by default.
- `VNC_PORT` (default 5901), `VNC_PASSWORD` (default `ayab`),
  `CONTAINER_NAME` (default `ayab`). Starting a script replaces any running
  container with the same name.

Audio goes to a PulseAudio server on the host, if one is running (see
`docker/Dockerfile`). Links opened by the app are shown in a dialog instead of
a browser (`docker/image/xdg-open`).

## Scripting the display

The image includes `xdotool` and `maim`, so the running app can be driven and
captured from the host, e.g. to open the File menu and take a screenshot:

    docker exec ayab xdotool key alt+f
    docker exec ayab maim > screenshot.png

## The image

`docker/Dockerfile` (Debian trixie with Python 3.11) has Wine 10 with Windows
Python, and Linux Python, each with AYAB's dependencies. Its entrypoint,
`docker/image/ayab-entrypoint`, starts the VNC display (`start-vnc-display`:
Xvfb, Openbox and x11vnc on port 5900) and then runs, depending on its first
argument:

| Argument            | Runs                                                       |
| ------------------- | ---------------------------------------------------------- |
| `source-linux`      | the checkout mounted at `/workspace`, with Linux Python    |
| `source-wine`       | the checkout mounted at `/workspace`, with Windows Python  |
| `path/to/*.AppImage` | a Linux AppImage                                          |
| `path/to/*.exe`     | a Windows program under Wine; a release installer is unpacked first |

To use it without the scripts, from the repository root:

    docker build --platform linux/amd64 --file docker/Dockerfile --target runner --tag ayab .
    docker run --rm --platform linux/amd64 --publish 127.0.0.1:5901:5900 \
      --mount type=bind,source="$PWD",target=/workspace ayab source-wine

and connect a VNC viewer to `127.0.0.1:5901` (password `ayab`).

`docker/vnc-session.sh` holds what the host scripts share: building the image,
starting the container, waiting for the AYAB window and opening the viewer.
The same Dockerfile also cross-builds the Windows application, see
`windows-build/README.md`.
