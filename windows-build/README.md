# windows-build

To run AYAB under Wine (a Windows release, or this checkout with Windows
Python), use `windows-build/run-release.sh` and `windows-build/run-source.sh`;
see `docker/README.md`.

## Cross-build with Docker

The `wine-source` image (see `docker/README.md`) can also build the Windows
application from this checkout: `fbs freeze` runs 64-bit Windows Python and
PyInstaller under Wine. It produces the unpacked application bundle only; NSIS
is not installed or run.

fbs uses the version as a Windows file version, so it must contain exactly
three numeric components. Like CI (`.github/actions/init-environment`), set it
in the checkout first, then, from the repository root:

    sed -i.bak -e 's/PACKAGE_VERSION/1.1.0/' src/build/settings/base.json
    echo 1.1.0 > src/main/resources/base/ayab/package_version
    docker build --platform linux/amd64 --file docker/Dockerfile \
      --target wine-source --tag ayab-wine-source .
    docker run --rm --platform linux/amd64 \
      --mount type=bind,source="$PWD",target=/workspace \
      --mount type=volume,source=ayab-venvs,target=/venvs \
      ayab-wine-source source-wine freeze

The executable is written to `target/AYAB/AYAB.exe`. Distribute the whole
`AYAB` directory because the executable depends on its `_internal` directory.
`windows-build/run-release.sh target/AYAB/AYAB.exe` runs it. On Apple Silicon,
`--platform linux/amd64` runs the image through Docker Desktop's amd64
emulation.

The image uses Windows Python 3.11.9, matching the native Windows CI; override
it with `--build-arg PYTHON_VERSION=x.y.z`.

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
