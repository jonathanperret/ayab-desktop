# syntax=docker/dockerfile:1
# check=skip=FromPlatformFlagConstDisallowed

# One image runs AYAB both natively on Linux and as the Windows build under
# Wine, on a virtual display served over VNC; see docker/README.md. Debian
# trixie provides Wine 10, and the python:3.11 base the Python version AYAB
# requires for Linux runs. Build with the repository root as the context:
#
#     docker build --file docker/Dockerfile --target runner --tag ayab .
#
# The builder and artifact targets cross-build the Windows application; see
# windows-build/README.md.

FROM --platform=linux/amd64 python:3.11-slim-trixie AS base

# Audio expects a PulseAudio server on the host; on macOS:
#     brew install pulseaudio
#     pulseaudio --exit-idle-time=-1 --load="module-native-protocol-tcp listen=127.0.0.1 port=4713 auth-anonymous=1"
ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PULSE_SERVER=tcp:host.docker.internal:4713 \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1 \
    APPIMAGE_EXTRACT_AND_RUN=1

# Virtual display, window manager and VNC server (see start-vnc-display);
# websockify serves noVNC; maim and xdotool take screenshots and send input
# with docker exec; 7zip unpacks Windows release installers; the rest is what
# Qt needs on Linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl unzip 7zip \
        xvfb xauth x11-utils x11vnc openbox websockify maim xdotool \
        libasound2t64 libasound2-plugins \
        libdbus-1-3 libegl1 libfontconfig1 libgl1 libglib2.0-0t64 \
        libgtk-3-0t64 libxkbcommon-x11-0 libxcb-cursor0 libxcb-icccm4 \
        libxcb-image0 libxcb-keysyms1 libxcb-randr0 libxcb-render-util0 \
        libxcb-shape0 libxcb-xinerama0 libxcb-xkb1 fonts-dejavu-core \
    && rm -rf /var/lib/apt/lists/*

RUN printf '%s\n' \
        'pcm.!default { type pulse }' \
        'ctl.!default { type pulse }' \
        > /etc/asound.conf

# noVNC browser client, served by websockify (see start-vnc-display)
COPY --chmod=0755 docker/image/install-novnc /tmp/install-novnc
RUN /tmp/install-novnc && rm /tmp/install-novnc

COPY --chmod=0755 docker/image/start-vnc-display /usr/local/bin/start-vnc-display
# Qt (and Wine's winebrowser) open URLs with xdg-open; show them in a dialog
COPY --chmod=0755 docker/image/xdg-open /usr/local/bin/xdg-open

EXPOSE 5900 6080

FROM base AS wine

ENV WINEARCH=win64 \
    WINEPREFIX=/wine \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml=

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        wine wine32:i386 wine64 fonts-wine \
    && rm -rf /var/lib/apt/lists/*

RUN xvfb-run -a sh -c \
        'wineboot --init \
        && wineserver -w'

FROM wine AS wine-python

ARG PYTHON_VERSION=3.11.9

# Build steps run Wine without a display
ENV DISPLAY=

RUN curl --fail --location --output /tmp/python.nupkg \
        "https://api.nuget.org/v3-flatcontainer/python/${PYTHON_VERSION}/python.${PYTHON_VERSION}.nupkg" \
    && unzip -q /tmp/python.nupkg -d /tmp/python \
    && mkdir -p /wine/drive_c/Python311 \
    && cp -a /tmp/python/tools/. /wine/drive_c/Python311/ \
    && rm -rf /tmp/python /tmp/python.nupkg \
    && wine C:\\Python311\\python.exe -m ensurepip --upgrade

RUN curl --fail --location --output /tmp/vclibs.appx \
        https://aka.ms/Microsoft.VCLibs.x64.14.00.Desktop.appx \
    && mkdir -p /wine/drive_c/VCRuntime \
    && unzip -q /tmp/vclibs.appx '*.dll' -d /wine/drive_c/VCRuntime \
    && rm /tmp/vclibs.appx \
    && test -f /wine/drive_c/VCRuntime/vccorlib140.dll

ENV WINEPATH=C:\\Python311;C:\\Python311\\Scripts;C:\\VCRuntime

WORKDIR /workspace

COPY requirements.build.txt windows-build/windows_build_requirements.txt /tmp/requirements/

# Windows pip cannot invoke the Linux git executable. Use the equivalent GitHub
# source archive for the commit-pinned fbs dependency.
RUN sed -E \
        's#^fbs @ git\+https://github.com/([^@]+)@([0-9a-f]+)$#fbs @ https://github.com/\1/archive/\2.zip#' \
        /tmp/requirements/requirements.build.txt > /tmp/requirements/windows.txt \
    && wine C:\\Python311\\python.exe -m pip install \
        -r Z:\\tmp\\requirements\\windows.txt \
        -r Z:\\tmp\\requirements\\windows_build_requirements.txt \
    && find /wine/drive_c/Python311/Lib/site-packages \
        -iname qopensslbackend.dll -delete

# Modern Windows supplies UCRT API-set contracts as part of the OS. The pinned
# fbs fork predates that baseline and incorrectly requires an SDK copy on PATH.
RUN sed -i \
        "s/for ucrt_dll in ('api-ms-win-crt-multibyte-l1-1-0.dll',):/for ucrt_dll in ():/" \
        /wine/drive_c/Python311/Lib/site-packages/fbs/freeze/windows.py

# Linux Python environment, built separately so that the compiler needed by
# simpleaudio stays out of the final image
FROM --platform=linux/amd64 python:3.11-slim-trixie AS linux-python

RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.build.txt /tmp/requirements/

# Same fbs source archive as for Windows, so git isn't needed
RUN --mount=type=cache,target=/root/.cache/pip \
    sed -E \
        's#^fbs @ git\+https://github.com/([^@]+)@([0-9a-f]+)$#fbs @ https://github.com/\1/archive/\2.zip#' \
        /tmp/requirements/requirements.build.txt > /tmp/requirements/linux.txt \
    && python -m venv /opt/venv \
    && /opt/venv/bin/pip install -r /tmp/requirements/linux.txt

FROM wine-python AS runner

ENV DISPLAY=:99

COPY --from=linux-python /opt/venv /opt/venv
COPY --chmod=0755 docker/image/ayab-entrypoint /usr/local/bin/ayab-entrypoint

ENTRYPOINT ["ayab-entrypoint"]
CMD ["source-linux"]

FROM wine-python AS builder

ARG APP_VERSION=0.0.0

COPY src /workspace/src

RUN find src/main/python -name '*_gui.ui' -print \
        | while IFS= read -r source; do \
            wine C:\\Python311\\Scripts\\pyside6-uic.exe \
                "$(winepath -w "$source")" \
                -o "$(winepath -w "${source%.ui}.py")"; \
        done \
    && find src/main/python -name '*_rc.qrc' -print \
        | while IFS= read -r source; do \
            wine C:\\Python311\\Scripts\\pyside6-rcc.exe \
                "$(winepath -w "$source")" \
                -o "$(winepath -w "${source%.qrc}.py")"; \
        done

RUN case "$APP_VERSION" in \
        *[!0-9.]*|*.*.*.*|.*|*.) echo "APP_VERSION must be numeric x.y.z" >&2; exit 2 ;; \
    esac \
    && test "$(printf '%s' "$APP_VERSION" | tr -cd '.' | wc -c)" -eq 2 \
    && mkdir -p src/main/resources/base/ayab \
    && printf '%s\n' "$APP_VERSION" > src/main/resources/base/ayab/package_version \
    && sed -i "s/PACKAGE_VERSION/$APP_VERSION/" src/build/settings/base.json \
    && xvfb-run -a wine C:\\Python311\\python.exe -m fbs freeze \
    && test -f target/AYAB/AYAB.exe

# The runner with the cross-built Windows application
FROM runner AS wine-ayab-runner

COPY --from=builder /workspace/target/AYAB /AYAB
CMD ["/AYAB/AYAB.exe"]

FROM scratch AS artifact
COPY --from=builder /workspace/target/AYAB /AYAB
