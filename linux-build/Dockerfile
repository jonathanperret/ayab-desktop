# This stage sets up the dependencies required to run AYAB, with the GUI on a
# virtual display served over VNC (port 5900) and audio (PulseAudio) exported
# to the host. linux-build/run-appimage.sh and linux-build/run-source.sh run it
# and open a VNC viewer.
FROM quay.io/pypa/manylinux_2_34_x86_64:2025.02.28-1 AS appimage-host

ENV QT_QPA_PLATFORM=xcb
ENV DISPLAY=:99

RUN yum install -qy double-conversion compat-openssl11 libxkbcommon-x11 \
    xcb-util-cursor xcb-util-keysyms xcb-util-wm alsa-plugins-pulseaudio \
    gtk3

# Virtual display, window manager and VNC server (see start-vnc-display),
# plus maim and xdotool to take screenshots and send input with docker exec
RUN yum install -qy epel-release \
    && yum install -qy xorg-x11-server-Xvfb xorg-x11-utils openbox x11vnc \
       maim xdotool

# Follow the GTK theme, so that DARK_MODE=1 (GTK_THEME=Adwaita:dark) applies.
ENV QT_QPA_PLATFORMTHEME=gtk3

# Expects a running PulseAudio server on the host machine
# On MacOS this can be achieved with:
#     brew install pulseaudio
#     pulseaudio --exit-idle-time=-1 --load="module-native-protocol-tcp listen=127.0.0.1 port=4713 auth-anonymous=1"
ENV PULSE_SERVER=tcp:host.docker.internal:4713

RUN printf '%s\n' \
    'pcm.!default { type pulse }' \
    'ctl.!default { type pulse }' \
    > /etc/asound.conf

# Without audio, use instead:
#RUN echo "pcm.!default = null;" > /etc/asound.conf

ENV APPIMAGE_EXTRACT_AND_RUN=1

# Qt opens URLs with xdg-open; show them in a dialog instead of a browser
RUN yum install -qy zenity
COPY --chmod=0755 docker/image/xdg-open /usr/local/bin/xdg-open

COPY --chmod=0755 docker/image/start-vnc-display /usr/local/bin/start-vnc-display
COPY --chmod=0755 linux-build/image/linux-entrypoint /entrypoint
ENTRYPOINT ["/entrypoint"]
EXPOSE 5900

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
