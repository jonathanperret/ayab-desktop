ARG PYTHON_VERSION=3.11.9
ARG PYSIDE_VERSION=6.6.2

FROM ubuntu:22.04 AS python-build

RUN rm -f /etc/apt/apt.conf.d/docker-clean

RUN apt-get update

# Python build dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get install -qy curl git build-essential zlib1g-dev libncurses5-dev libgdbm-dev \
      libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev
      RUN curl -Ssf https://pyenv.run | bash

FROM python-build AS python-3.11.8

RUN /root/.pyenv/bin/pyenv install --verbose 3.11.8

FROM python-build AS python-3.11.9

RUN /root/.pyenv/bin/pyenv install --verbose 3.11.9

FROM python-$PYTHON_VERSION AS python

FROM ubuntu:22.04 AS base

RUN rm -f /etc/apt/apt.conf.d/docker-clean

RUN apt-get update

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get install -qy file binutils

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get install -qy libasound2
RUN echo "pcm.!default = null;" > /etc/asound.conf

ENV QT_QPA_PLATFORM=vnc
ENV APPIMAGE_EXTRACT_AND_RUN=1

FROM base AS ayab-base

ARG PYTHON_VERSION

COPY --from=python /root/.pyenv/versions/ /root/.pyenv/versions/
RUN /root/.pyenv/versions/$PYTHON_VERSION/bin/python -mvenv --upgrade-deps /tmp/venv

ENV PATH=/tmp/venv/bin:$PATH VIRTUAL_ENV=/tmp/venv

RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get install -qy git g++ libasound-dev

RUN mkdir /ayab
WORKDIR /ayab

FROM ayab-base AS ayab-local

COPY requirements*.txt /ayab

COPY src /ayab/src
COPY mypy.ini /ayab/

FROM ayab-base AS ayab-github

#RUN git clone -b 1.0.0-dev https://github.com/AllYarnsAreBeautiful/ayab-desktop /ayab
RUN git clone -b misc-fixes https://github.com/jonathanperret/ayab-desktop /ayab

FROM ayab-github AS ayab-test

ARG PYSIDE_VERSION

RUN sed -i -E "s/^PySide6==.*/PySide6==${PYSIDE_VERSION}/" requirements.build.txt
RUN --mount=type=cache,target=/root/.cache/pip \
    pip install -r requirements.txt

# Qt6 system dependencies
RUN --mount=type=cache,target=/var/cache/apt,sharing=locked \
    apt-get install -qy --no-install-recommends \
      libegl1 \
      libevent-2.1-7 \
      libgbm1 \
      libgl1 \
      libglib2.0-0 \
      libminizip1 \
      libnspr4 \
      libnss3 \
      libopus0 \
      libpulse0 \
      libwebpdemux2 \
      libwebpmux3 \
      libxcomposite1 \
      libxdamage1 \
      libxkbcommon0 \
      libxkbfile1 \
      libxrandr2 \
      libxslt1.1 \
      libxtst6 \
      libdouble-conversion3 \
      libfontconfig1 \
      libpcsclite1 \
      libxi6
RUN ln -s libwebp.so.7 /usr/lib/$(uname -i)-linux-gnu/libwebp.so.6
# RUN pyside6-genpyi all

RUN cat setup-environment.ps1 | grep -v genpyi | bash -x

RUN mypy src

RUN sed -i -e s/PACKAGE_VERSION/1.0.0/ src/build/settings/base.json

ENV QT_QPA_PLATFORM=vnc:size=1600x1200
CMD ["fbs", "run"]
