#!/bin/sh
set -eu

: "${DISPLAY:=:99}"
export DISPLAY

if [ "$#" -eq 0 ]; then
    set -- AYAB.exe
fi

start-vnc-display

# Light mode with Qt's native Windows style by default. With DARK_MODE=1, set
# the Windows dark-mode preference and use Fusion, the Qt style that follows
# it (at the cost of no visible menu bar highlight when Alt is pressed).
if [ "${DARK_MODE:-0}" = 1 ]; then
    apps_use_light_theme=0
    export WINEQT_STYLE_OVERRIDE=Fusion
else
    apps_use_light_theme=1
    unset WINEQT_STYLE_OVERRIDE
fi
wine reg add "HKCU\Software\Microsoft\Windows\CurrentVersion\Themes\Personalize" \
    /v AppsUseLightTheme /t REG_DWORD /d "$apps_use_light_theme" /f

# A release installer (e.g. a mounted AYAB-x.y.z.exe) is unpacked into the
# prefix, then the application is run with the remaining arguments. The NSIS
# installer is 32-bit and fails to start under amd64 emulation, so 7-Zip
# extracts its payload instead of running it.
if [ -f "$1" ] && grep -q NullsoftInst "$1"; then
    installer=$1
    shift
    appdir="/wine/drive_c/Program Files/AYAB"
    rm -rf "$appdir"
    7z x -bd -o"$appdir" "$installer" >/dev/null
    rm -rf "$appdir/\$PLUGINSDIR"
    if [ ! -f "$appdir/AYAB.exe" ]; then
        echo "AYAB.exe not found in $installer" >&2
        exit 1
    fi
    cd "$appdir"
    set -- AYAB.exe "$@"
fi

exec /usr/lib/wine/wine64 "$@"
