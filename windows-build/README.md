# windows-build

To run AYAB under Wine (a Windows release, or this checkout with Windows
Python), use `windows-build/run-release.sh` and `windows-build/run-source.sh`;
see `docker/README.md`.

## Cross-build with Docker

`docker/Dockerfile` can also build the Windows application: it runs 64-bit
Windows Python and PyInstaller under Wine. It produces the unpacked application
bundle only; NSIS is not installed or run.

From the repository root:

    docker build --platform linux/amd64 \
      --file docker/Dockerfile \
      --target artifact \
      --build-arg APP_VERSION=1.1.0 \
      --output type=local,dest=target/windows .

The executable is written to `target/windows/AYAB/AYAB.exe`. Distribute the
whole `AYAB` directory because the executable depends on its `_internal`
directory. On Apple Silicon, `--platform linux/amd64` runs the image through
Docker Desktop's amd64 emulation.

`APP_VERSION` must contain exactly three numeric components because fbs uses it
as a Windows file version. The image defaults to Python 3.11.9, matching the
native Windows CI; override it with `--build-arg PYTHON_VERSION=x.y.z`.

The `wine-ayab-runner` target is the runner image with the cross-built
application added, started by default:

    docker build --platform linux/amd64 \
      --file docker/Dockerfile \
      --target wine-ayab-runner \
      --tag ayab-windows-build \
      --build-arg APP_VERSION=1.1.0 .
    docker run --rm --platform linux/amd64 \
      --publish 127.0.0.1:6080:6080 --publish 127.0.0.1:5901:5900 \
      ayab-windows-build

Then open `http://127.0.0.1:6080/vnc.html?autoconnect=1&resize=scale`
(password `ayab`), or connect a VNC viewer to `127.0.0.1:5901`.

## Native Windows build

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
