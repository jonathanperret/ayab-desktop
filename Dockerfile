FROM quay.io/pypa/manylinux_2_34_aarch64:2025.02.28-1 AS stage1

RUN yum install -qy alsa-lib-devel

ENV QT_QPA_PLATFORM=vnc
ENV APPIMAGE_EXTRACT_AND_RUN=1

RUN python3.11 -mvenv /tmp/venv

ENV PATH=/tmp/venv/bin:$PATH \
    VIRTUAL_ENV=/tmp/venv

RUN mkdir /ayab-src
WORKDIR /ayab-src

COPY requirements*.txt /ayab-src

FROM stage1 AS build

RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.build.txt

COPY src /ayab-src/src
COPY setup-environment.ps1 /ayab-src/

RUN cat setup-environment.ps1 | grep -v genpyi | grep -v submodule | bash -x

RUN sed -i -e s/PACKAGE_VERSION/1.0.0/ src/build/settings/base.json

#ENV QT_QPA_PLATFORM=vnc:size=1600x1200
ENV QT_QPA_PLATFORM=xcb
ENV DISPLAY=host.docker.internal:0

ENV PYTHONDONTWRITEBYTECODE=1

RUN yum install -qy double-conversion compat-openssl11 libxkbcommon-x11 xcb-util-cursor xcb-util-keysyms xcb-util-wm
RUN echo "pcm.!default = null;" > /etc/asound.conf

CMD ["fbs", "run"]
