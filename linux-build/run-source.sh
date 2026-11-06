#!/bin/sh
# Run this source checkout with Linux Python in Docker (fbs run) and open its
# display in the browser (noVNC). The checkout is mounted, so source changes
# are picked up on each launch. See docker/README.md for environment variables.
#
# Usage: linux-build/run-source.sh [fbs run arguments...]
set -eu

. "$(dirname "$0")/../docker/vnc-session.sh"

# Native: arm64 on Apple Silicon, without emulation
build_image linux-source native
run_in_vnc "source checkout (Linux)" \
    --mount "type=bind,source=$repo,target=/workspace" \
    --mount "type=volume,source=$venvs_volume,target=/venvs" \
    "$image" source-linux run "$@"
