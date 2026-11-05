#!/bin/sh
# Run this source checkout with Linux Python in Docker (fbs run) and open a VNC
# viewer on it. The checkout is mounted, so source changes are picked up on
# each launch. See docker/README.md for environment variables.
#
# Usage: linux-build/run-source.sh [fbs run arguments...]
set -eu

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image
run_in_vnc "source checkout (Linux)" \
    --mount "type=bind,source=$repo,target=/workspace" \
    "$image" source-linux "$@"
