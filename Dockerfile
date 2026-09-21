# This stage sets up the dependencies required to run AYAB
# with the GUI (X11) and audio (PulseAudio) exported to the host.
FROM quay.io/pypa/manylinux_2_34_x86_64:2025.02.28-1 AS appimage-host

ENV QT_QPA_PLATFORM=xcb
ENV DISPLAY=host.docker.internal:0

RUN yum install -qy double-conversion compat-openssl11 libxkbcommon-x11 \
        xcb-util-cursor xcb-util-keysyms xcb-util-wm alsa-plugins-pulseaudio

# Expects a running PulseAudio server on the host machine
# On MacOS this can be achieved with:
#     brew install pulseaudio
#     pulseaudio --exit-idle-time=-1 --load="module-native-protocol-tcp listen=127.0.0.1 port=4713 auth-anonymous=1"
ENV PULSE_SERVER=tcp:host.docker.internal:4713

RUN printf '%s\n' \
    'pcm.!default { type pulse }' \
    'ctl.!default { type pulse }' \
    > /etc/asound.conf

# Alternatively, for a headless setup without audio:
#ENV QT_QPA_PLATFORM=vnc:size=1600x1200
#RUN echo "pcm.!default = null;" > /etc/asound.conf

ENV APPIMAGE_EXTRACT_AND_RUN=1

# Add an entrypoint to auto-fix and run a passed AppImage
# See https://github.com/AppImage/AppImageKit/issues/828 for details.
RUN printf '%s\n' \
    '#!/bin/bash -xe' \
    'if [[ "$1" == *.AppImage ]]; then' \
    '    appimage="$(basename "$1")"' \
    '    cp "$1" "/tmp/$appimage"' \
    '    dd if=/dev/zero bs=1 count=3 seek=8 conv=notrunc of="/tmp/$appimage"' \
    '    cd /tmp' \
    '    shift' \
    '    exec "./$appimage" "$@"' \
    'fi' \
    'exec "$@"' \
    > /entrypoint \
    && chmod +x /entrypoint

ENTRYPOINT ["/entrypoint"]

# This stage actually runs AYAB from source
FROM appimage-host AS build

RUN yum install -qy alsa-lib-devel

RUN python3.11 -mvenv /tmp/venv

ENV PATH=/tmp/venv/bin:$PATH \
VIRTUAL_ENV=/tmp/venv

RUN mkdir /ayab-src
WORKDIR /ayab-src

COPY requirements*.txt /ayab-src

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.build.txt

COPY src /ayab-src/src
COPY setup-environment.ps1 /ayab-src/

RUN cat setup-environment.ps1 | grep -v genpyi | grep -v submodule | bash -x

RUN sed -i -e s/PACKAGE_VERSION/1.0.0/ src/build/settings/base.json

ENV PYTHONDONTWRITEBYTECODE=1

CMD ["fbs", "run"]
