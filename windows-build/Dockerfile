# Wine provides the Windows runtime while Docker makes the build reproducible
# on Linux and macOS. This base supports both frozen and source-based runs.

# syntax=docker/dockerfile:1
# check=skip=FromPlatformFlagConstDisallowed

# wine-base is the base Wine image
FROM --platform=linux/amd64 debian:trixie-slim AS wine-base

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PULSE_SERVER=tcp:host.docker.internal:4713 \
    WINEARCH=win64 \
    WINEPREFIX=/wine \
    WINEDEBUG=-all \
    WINEDLLOVERRIDES=mscoree,mshtml= \
    PYTHONUTF8=1 \
    PYTHONUNBUFFERED=1

RUN dpkg --add-architecture i386 \
    && apt-get update \
    && apt-get install -y --no-install-recommends \
        ca-certificates curl openbox unzip wine wine32:i386 wine64 fonts-wine \
        x11-utils x11vnc xauth xvfb \
    && rm -rf /var/lib/apt/lists/*

RUN xvfb-run -a sh -c \
        'wineboot --init \
        && wineserver -w'

EXPOSE 5900

FROM wine-base AS wine-python

ARG PYTHON_VERSION=3.11.9

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

FROM wine-python AS source-runner

ENV WINEQT_QPA_PLATFORM=windows:darkmode=2 \
    WINEQT_STYLE_OVERRIDE=Fusion

COPY --chmod=0755 windows-build/run-wine.sh /usr/local/bin/run-wine

CMD ["run-wine", "C:\\Python311\\python.exe", "-m", "fbs", "run"]

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

FROM wine-base AS wine-runner

COPY --chmod=0755 windows-build/run-wine.sh /usr/local/bin/run-wine

ENTRYPOINT ["run-wine"]

FROM wine-runner AS wine-ayab-runner

COPY --from=builder /workspace/target/AYAB /AYAB
WORKDIR /AYAB
CMD ["AYAB.exe"]

FROM scratch AS artifact
COPY --from=builder /workspace/target/AYAB /AYAB
