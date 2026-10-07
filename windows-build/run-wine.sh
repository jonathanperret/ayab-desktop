#!/bin/sh
set -eu

: "${VNC_PASSWORD:=ayab}"
: "${DISPLAY:=:99}"
export DISPLAY

if [ "$#" -eq 0 ]; then
    set -- AYAB.exe
fi

Xvfb "$DISPLAY" -screen 0 1440x900x24 -nolisten tcp &

attempts=0
until xdpyinfo -display "$DISPLAY" >/dev/null 2>&1; do
    attempts=$((attempts + 1))
    if [ "$attempts" -ge 50 ]; then
        echo "Xvfb did not become ready" >&2
        exit 1
    fi
    sleep 0.1
done

openbox &
x11vnc \
    -display "$DISPLAY" \
    -forever \
    -shared \
    -passwd "$VNC_PASSWORD" \
    -rfbport 5900 \
    -listen 0.0.0.0 &

# To enable dark mode:
wine reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" /v AppsUseLightTheme /t REG_DWORD /d 0 /f
export WINEQT_STYLE_OVERRIDE=Fusion

exec /usr/lib/wine/wine64 "$@"
