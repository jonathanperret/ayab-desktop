#!/bin/sh
# Run this source checkout with Windows Python under Wine in Docker (fbs run)
# and open a VNC viewer on it. The checkout is mounted, so source changes are
# picked up on each launch; the image is only rebuilt when dependencies
# change. See docker/vnc-session.sh for environment variables.
#
# Usage: windows-build/run-source.sh
set -eu

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image windows-build/Dockerfile source-runner ayab-windows-source
run_in_vnc "source checkout" \
    --mount "type=bind,source=$repo,target=/workspace" \
    ayab-windows-source
