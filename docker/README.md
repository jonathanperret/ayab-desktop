# Running AYAB in Docker

These scripts run AYAB in a Linux container, either natively on Linux or as the
Windows build under Wine, and open a VNC viewer on it: TigerVNC if installed
(`brew install --cask tigervnc-viewer`), otherwise macOS Screen Sharing. Run
them from anywhere; they build the image they need first (cached after the
first time).

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
`linux-build/Dockerfile`). Links opened by the app are shown in a dialog instead of a
browser (`docker/image/xdg-open`).

## Scripting the display

The images include `xdotool` and `maim`, so the running app can be driven and
captured from the host, e.g. to open the File menu and take a screenshot:

    docker exec ayab xdotool key alt+f
    docker exec ayab maim > screenshot.png

## Layout

- `docker/`: shared by the Linux and Wine setups. `image/` holds files
  installed in both images (`start-vnc-display` runs Xvfb, Openbox and
  x11vnc; `xdg-open`); `vnc-session.sh` is used by the host scripts to start
  the container, wait for the AYAB window and open the viewer.
- `linux-build/`: `Dockerfile` (`appimage-host` and `build` targets), the
  image's entrypoint in `image/`, and the `run-*.sh` host scripts.
- `windows-build/`: the same for Wine, see `windows-build/README.md`.

The images are built with the repository root as the context, e.g.
`docker build --file linux-build/Dockerfile --target build .`
