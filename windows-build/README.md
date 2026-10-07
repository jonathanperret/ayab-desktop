# windows-build

## Cross-build with Docker

The Docker build runs 64-bit Windows Python and PyInstaller under Wine. It
produces the unpacked application bundle only; NSIS is not installed or run.

From the repository root:

    docker build --platform linux/amd64 \
      --file windows-build/Dockerfile \
      --build-arg APP_VERSION=1.1.0 \
      --output type=local,dest=target/windows .

The executable is written to `target/windows/AYAB/AYAB.exe`. Distribute the
whole `AYAB` directory because the executable depends on its `_internal`
directory. On Apple Silicon, `--platform linux/amd64` runs the image through
Docker Desktop's amd64 emulation.

`APP_VERSION` must contain exactly three numeric components because fbs uses it
as a Windows file version. The image defaults to Python 3.11.9, matching the
native Windows CI; override it with `--build-arg PYTHON_VERSION=x.y.z`.

## Run with Wine and VNC

The `wine-runner` target uses Wine 10, initializes its prefix during the image
build, and enables the Windows dark-mode preferences used by Qt. AYAB runs on
an Openbox-managed virtual display exposed through an authenticated VNC server.

  docker build --platform linux/amd64 \
    --target wine-runner \
    --tag ayab-windows-wine \
    --file windows-build/Dockerfile \
    --build-arg APP_VERSION=1.1.0 .

On macOS, install and start a PulseAudio server for Wine to use:

  brew install pulseaudio
  pulseaudio --exit-idle-time=-1 \
    --load="module-native-protocol-tcp listen=127.0.0.1 port=4713 auth-anonymous=1"

Then run the application with the VNC port bound to localhost:

  docker run --rm --platform linux/amd64 \
    --name ayab-wine \
    --publish 127.0.0.1:5901:5900 \
    --env VNC_PASSWORD=ayab \
    ayab-windows-wine

Connect a VNC client to `127.0.0.1:5901`. On macOS, open
`vnc://127.0.0.1:5901` in Screen Sharing and enter the value supplied through
`VNC_PASSWORD`.

## Run source with Wine and VNC

Build the development image once. This target installs Windows Python and the
application dependencies, but stops before copying the source or running
`fbs freeze`:

  docker build --platform linux/amd64 \
    --target source-runner \
    --tag ayab-windows-source \
    --file windows-build/Dockerfile .

Run it from the repository root with the checkout mounted at `/workspace`:

  docker run --rm --platform linux/amd64 \
    --name ayab-wine-source \
    --publish 127.0.0.1:5901:5900 \
    --env VNC_PASSWORD=ayab \
    --mount type=bind,source="$PWD",target=/workspace \
    ayab-windows-source

The container runs `fbs run` with Windows Python under Wine. Python source
changes are picked up on the next container launch without rebuilding the
image. Rebuild the source image only when Python or system dependencies change.

To build a binary from the Python script files, use PyInstaller (pip install pyinstaller) inside the virtualenv:

    cd ayab-desktop
    venv\Scripts\activate
    python3 -m fbs freeze

This will generate a standalone build inside target/AYAB
To build the NSIS installer, run 
    
    python3 -m fbs installer

(NSIS must be on the Windows PATH)

## Win10 Build dependencies

* vcredist packages
  * https://www.microsoft.com/en-us/download/confirmation.aspx?id=26999
  * https://www.microsoft.com/en-us/download/confirmation.aspx?id=30679
  * https://www.microsoft.com/en-us/download/confirmation.aspx?id=48145
  * https://developer.microsoft.com/en-us/windows/downloads/windows-10-sdk

* git for windows (https://git-scm.com/download/win)
* python 3.5.3 (64 bit) (https://www.python.org/downloads/release/python-353/)
* NSIS http://nsis.sourceforge.net/Download
* gitlab-runner (https://docs.gitlab.com/runner/install/windows.html)

## Settings

* Add to Path
  * C:\Programs and Files\Git\bin\
  * NSIS
  * %SystemRoot%/SysWOW64

* config.toml
  * executor = "shell"
  * shell = "bash"
  * build_dir = "/c/gitlab-runner/builds/"
  * builds_cache = "/c/gitlab-runner/cache/"

## Gitlab Runner Call
C:\Program Files\Git\bin\bash.exe -c "/c/gitlab-runner/gitlab-runner.exe run --working-directory /c/gitlab-runner --config /c/gitlab-runner/config.toml --service gitlab-runner --syslog"
