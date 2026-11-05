#!/bin/sh
# Run an AYAB Linux AppImage in Docker and open a VNC viewer on it.
# See docker/vnc-session.sh for environment variables.
#
# Usage: linux-build/run-appimage.sh path/to/AYAB-x.y.z-x86_64.AppImage [AYAB arguments...]
set -eu

if [ "$#" -lt 1 ] || [ ! -f "$1" ] || [ "${1%.AppImage}" = "$1" ]; then
    echo "Usage: $0 path/to/AYAB-x.y.z-x86_64.AppImage [AYAB arguments...]" >&2
    exit 2
fi

appimage=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
shift

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image linux-build/Dockerfile appimage-host ayab-appimage-host
run_in_vnc "$(basename "$appimage")" \
    --mount "type=bind,source=$appimage,target=/app/$(basename "$appimage"),readonly" \
    ayab-appimage-host "/app/$(basename "$appimage")" "$@"
