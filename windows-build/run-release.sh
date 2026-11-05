#!/bin/sh
# Run a downloaded AYAB Windows release installer under Wine in Docker and
# open a VNC viewer on it. See docker/README.md for environment variables.
#
# Usage: windows-build/run-release.sh path/to/AYAB-x.y.z.exe [AYAB arguments...]
set -eu

if [ "$#" -lt 1 ] || [ ! -f "$1" ]; then
    echo "Usage: $0 path/to/AYAB-x.y.z.exe [AYAB arguments...]" >&2
    exit 2
fi

installer=$(cd "$(dirname "$1")" && pwd)/$(basename "$1")
shift

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image
run_in_vnc "$(basename "$installer")" \
    --mount "type=bind,source=$installer,target=/installer.exe,readonly" \
    "$image" /installer.exe "$@"
