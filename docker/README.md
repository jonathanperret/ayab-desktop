# Running AYAB in Docker

These scripts run AYAB in a Linux container, either natively on Linux or as the
Windows build under Wine, and open the app's display in your web browser with
[noVNC](https://novnc.com), so no VNC client needs to be installed. Run them
from anywhere. Each builds the image it needs from `docker/Dockerfile` on
launch (cached after the first time).

Source runs mount the checkout, so changes are picked up on the next launch.
Their Python environment lives in a Docker volume (`ayab-venvs`): the first
run creates it, which takes a while, and later runs update it when the
requirements change. Qt modules generated from `.ui` and `.qrc` files are
regenerated in the checkout when missing or out of date. Arguments are passed
to `fbs run`. The `wine-source` image can also cross-build the Windows
application; see `windows-build/README.md`.

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
- `NOVNC_PORT` (default 6080): the noVNC page,
  `http://127.0.0.1:6080/vnc.html`. The scripts open it with the password
  filled in and the display scaled to fit the browser window.
- `VNC_PORT` (default 5901): the VNC server, for a native client such as
  macOS Screen Sharing (`open vnc://127.0.0.1:5901`) or TigerVNC.
- `VNC_PASSWORD` (default `ayab`), `CONTAINER_NAME` (default `ayab`).
  Starting a script replaces any running container with the same name.
- `VENVS_VOLUME` (default `ayab-venvs`): the volume holding the source runs'
  Python environments. `docker volume rm ayab-venvs` starts over.

Both ports are bound to localhost only.

Audio goes to a PulseAudio server on the host, if one is running (see
`docker/Dockerfile`). Links opened by the app are shown in a dialog instead of
a browser (`docker/image/xdg-open`).

## Scripting the display

The images include `xdotool` and `maim`, so the running app can be driven and
captured from the host, e.g. to open the File menu and take a screenshot:

    docker exec ayab xdotool key alt+f
    docker exec ayab maim > screenshot.png

## The images

`docker/Dockerfile` (Debian trixie with Python 3.11) builds four images, none
of which contains AYAB code or dependencies:

| Target          | Adds to the shared base                    | Runs                                |
| --------------- | ------------------------------------------ | ----------------------------------- |
| `linux-release` | nothing                                    | `path/to/*.AppImage`                |
| `linux-source`  | a compiler, to build the environment       | `source-linux [fbs command]`        |
| `wine-release`  | Wine 10                                    | `path/to/*.exe`; a release installer is unpacked first |
| `wine-source`   | Wine 10 and a plain Windows Python 3.11    | `source-wine [fbs command]`         |

Source images run the checkout mounted at `/workspace` and keep their Python
environment in `/venvs`. The shared entrypoint, `docker/image/ayab-entrypoint`,
starts the display (`start-vnc-display`: Xvfb, Openbox, x11vnc on port 5900,
and websockify serving noVNC on port 6080; noVNC is a pinned release
installed by `docker/image/install-novnc`), then runs its argument.

To use one without the scripts, from the repository root:

    docker build --platform linux/amd64 --file docker/Dockerfile --target wine-source --tag ayab-wine-source .
    docker run --rm --platform linux/amd64 \
      --publish 127.0.0.1:6080:6080 --publish 127.0.0.1:5901:5900 \
      --mount type=bind,source="$PWD",target=/workspace \
      --mount type=volume,source=ayab-venvs,target=/venvs ayab-wine-source

and open `http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale` (password
`ayab`), or connect a VNC viewer to `127.0.0.1:5901`.

CI (`.github/workflows/docker-image.yml`) checks that AYAB starts in each
image and pushes them as `ghcr.io/<owner>/ayab-<target>`.

`docker/vnc-session.sh` holds what the host scripts share: building the image,
starting the container, waiting for the AYAB window and opening noVNC in the
browser.
