FROM ubuntu:22.04 as base

RUN apt-get update

RUN apt-get install -qy file binutils

RUN apt-get install -qy libasound2
RUN echo "pcm.!default = null;" > /etc/asound.conf

ENV QT_QPA_PLATFORM=vnc
ENV APPIMAGE_EXTRACT_AND_RUN=1

RUN apt-get install -qy --no-install-recommends gnupg
RUN echo 'deb https://ppa.launchpadcontent.net/deadsnakes/ppa/ubuntu jammy main' > /etc/apt/sources.list.d/deadsnakes.list
RUN apt-key adv --keyserver keyserver.ubuntu.com --recv-keys F23C5A6CF475977595C89F51BA6932366A755776

RUN apt update

RUN apt-get install -qy python3.11-venv

# Qt6 system dependencies
RUN apt-get install -qy --no-install-recommends \
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

FROM base as python

RUN python3.11 -mvenv /tmp/venv

ENV PATH=/tmp/venv/bin:$PATH VIRTUAL_ENV=/tmp/venv

RUN pip install PySide6==6.6.3
RUN pip install pyserial==3.5

RUN apt-get install -qy socat
