# syntax=docker/dockerfile:1
# check=skip=FromPlatformFlagConstDisallowed

# Images that run AYAB on a virtual display served over VNC and noVNC; see
# docker/README.md. They contain no AYAB code: release images run a given
# AppImage or Windows executable, source images run a checkout mounted at
# /workspace, with Python environments created and updated at runtime in
# /venvs (see ayab-entrypoint).
#
#   linux-release   runs a Linux AppImage
#   linux-source    runs a checkout with Linux Python
#   wine-release    runs a Windows executable (or release installer) under Wine
#   wine-source     runs a checkout with Windows Python under Wine
#
# Build from the repository root, e.g.:
#
#     docker build --file docker/Dockerfile --target wine-source --tag ayab-wine-source .

# Debian trixie provides Wine 10; the python:3.11 base provides the Python
# version AYAB requires on Linux (unused by the release images).
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
# with docker exec; the rest is what Qt needs on Linux
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl \
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
COPY --chmod=0755 docker/image/ayab-entrypoint /usr/local/bin/ayab-entrypoint

ENTRYPOINT ["ayab-entrypoint"]
EXPOSE 5900 6080

FROM base AS linux-release

FROM base AS linux-source

# To build the Python packages that have no wheel (simpleaudio)
RUN apt-get update \
    && apt-get install -y --no-install-recommends gcc libc6-dev libasound2-dev \
    && rm -rf /var/lib/apt/lists/*

CMD ["source-linux"]

FROM base AS wine-release

ENV WINEARCH=win64 \
    WINEPREFIX=/wine \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml=

# 7zip unpacks release installers
RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        wine wine32:i386 wine64 fonts-wine 7zip \
    && rm -rf /var/lib/apt/lists/*

# Remove the build-time X server's files, whose stale lock would otherwise
# stop the display from starting in containers (see start-vnc-display)
RUN xvfb-run -a sh -c \
        'wineboot --init \
        && wineserver -w' \
    && rm -rf /tmp/.X*-lock /tmp/.X11-unix /tmp/wine-*

FROM wine-release AS wine-source

ARG PYTHON_VERSION=3.11.9

# Plain Windows Python, copied to /venvs/wine and completed with AYAB's
# requirements at runtime (see ayab-entrypoint)
RUN apt-get update \
    && apt-get install -y --no-install-recommends unzip \
    && rm -rf /var/lib/apt/lists/* \
    && curl --fail --location --output /tmp/python.nupkg \
        "https://api.nuget.org/v3-flatcontainer/python/${PYTHON_VERSION}/python.${PYTHON_VERSION}.nupkg" \
    && unzip -q /tmp/python.nupkg -d /tmp/python \
    && mkdir -p /wine/drive_c/Python311 \
    && cp -a /tmp/python/tools/. /wine/drive_c/Python311/ \
    && rm -rf /tmp/python /tmp/python.nupkg \
    && DISPLAY= wine C:\\Python311\\python.exe -m ensurepip --upgrade

RUN curl --fail --location --output /tmp/vclibs.appx \
        https://aka.ms/Microsoft.VCLibs.x64.14.00.Desktop.appx \
    && mkdir -p /wine/drive_c/VCRuntime \
    && unzip -q /tmp/vclibs.appx '*.dll' -d /wine/drive_c/VCRuntime \
    && rm /tmp/vclibs.appx \
    && test -f /wine/drive_c/VCRuntime/vccorlib140.dll

ENV WINEPATH=C:\\VCRuntime

CMD ["source-wine"]
