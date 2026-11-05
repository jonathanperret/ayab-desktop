#!/bin/sh
# Run this source checkout with Windows Python under Wine in Docker (fbs run)
# and open its display in the browser (noVNC). The checkout is mounted, so
# source changes are picked up on each launch. See docker/README.md for
# environment variables.
#
# Usage: windows-build/run-source.sh [fbs run arguments...]
set -eu

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image wine-source
run_in_vnc "source checkout (Wine)" \
    --mount "type=bind,source=$repo,target=/workspace" \
    --mount "type=volume,source=$venvs_volume,target=/venvs" \
    "$image" source-wine run "$@"
