#!/bin/sh
# Run this source checkout on Linux in Docker (fbs run) and open a VNC viewer
# on it. The source is copied into the image, so the image is rebuilt on each
# launch (dependency layers stay cached). See docker/vnc-session.sh for
# environment variables.
#
# Usage: linux-build/run-source.sh
set -eu

. "$(dirname "$0")/../docker/vnc-session.sh"

build_image linux-build/Dockerfile build ayab-linux-source
run_in_vnc "source checkout" ayab-linux-source
