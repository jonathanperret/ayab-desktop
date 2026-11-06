# Sourced (not executed) by the run-*.sh scripts in linux-build/ and
# windows-build/: run AYAB in a container of the image built from
# docker/Dockerfile, whose display is served over VNC (see
# docker/image/start-vnc-display), and open that display in the browser with
# noVNC.
#
# Environment: NOVNC_PORT (default 6080), VNC_PORT (default 5901, for native
#              VNC clients), VNC_PASSWORD (default ayab), CONTAINER_NAME
#              (default ayab), DARK_MODE (default 0; 1 for dark mode),
#              VENVS_VOLUME (default ayab-venvs, for source runs)

: "${NOVNC_PORT:=6080}"
: "${VNC_PORT:=5901}"
: "${VNC_PASSWORD:=ayab}"
: "${CONTAINER_NAME:=ayab}"
repo=$(cd "$(dirname "$0")/.." && pwd)

# build_image TARGET [PLATFORM]: build one of docker/Dockerfile's images (quick
# when nothing changed) for PLATFORM (default linux/amd64; "native" for the
# host's) and set $image to its tag, ayab-TARGET
build_image() {
    image=ayab-$1
    case ${2:-linux/amd64} in
        native) platform_args= ;;
        *) platform_args="--platform ${2:-linux/amd64}" ;;
    esac
    echo "Building $image image..."
    # shellcheck disable=SC2086
    docker build --quiet $platform_args \
        --file "$repo/docker/Dockerfile" \
        --target "$1" \
        --tag "$image" \
        "$repo" >/dev/null
}

# Source runs keep their Python environments in this volume between runs
venvs_volume=${VENVS_VOLUME:-ayab-venvs}

container_running() {
    docker ps --quiet --filter "name=^$CONTAINER_NAME\$" | grep -q .
}

# run_in_vnc DESCRIPTION [docker run options...] IMAGE [command...]
run_in_vnc() {
    description=$1
    shift

    docker rm --force "$CONTAINER_NAME" >/dev/null 2>&1 || true

    echo "Starting $description in container $CONTAINER_NAME..."
    # shellcheck disable=SC2086
    docker run --detach --rm $platform_args \
        --name "$CONTAINER_NAME" \
        --publish "127.0.0.1:$NOVNC_PORT:6080" \
        --publish "127.0.0.1:$VNC_PORT:5900" \
        --env VNC_PASSWORD="$VNC_PASSWORD" \
        --env DARK_MODE="${DARK_MODE:-0}" \
        "$@" >/dev/null

    # Show the log from the start: the first source run spends a while
    # setting up its Python environment
    echo "Following logs; press Ctrl-C to stop the container."
    trap 'docker stop "$CONTAINER_NAME" >/dev/null 2>&1; exit 0' INT TERM
    docker logs --follow "$CONTAINER_NAME" 2>&1 | grep -vE 'x11vnc|^[0-9]{2}/[0-9]{2}/[0-9]{4} ' &

    # x11vnc prints its port once it accepts connections; websockify starts
    # right after it
    novnc_url="http://127.0.0.1:$NOVNC_PORT/vnc.html"
    until docker logs "$CONTAINER_NAME" 2>&1 | grep -q '^PORT=' \
            && curl --silent --fail --output /dev/null "$novnc_url"; do
        if ! container_running; then
            echo "Container exited before VNC was ready" >&2
            exit 1
        fi
        sleep 1
    done

    # Startup under emulation is slow; wait for the AYAB window so the viewer
    # does not open on an empty black desktop
    echo "Waiting for the AYAB window..."
    until docker exec "$CONTAINER_NAME" sh -c \
            'xwininfo -root -tree -display "${DISPLAY:-:99}" | grep -qE "\"(AYAB|All Yarns Are Beautiful)"' 2>/dev/null; do
        if ! container_running; then
            echo "Container exited before AYAB started" >&2
            exit 1
        fi
        sleep 2
    done

    open_viewer
    wait
}

open_viewer() {
    # The password in the URL lets noVNC connect without prompting. The ports
    # are bound to localhost only, but the URL lands in the browser history.
    url="$novnc_url?autoconnect=1&resize=scale&password=$VNC_PASSWORD"
    echo "Opening noVNC: $url"
    echo "(Native VNC clients: vnc://127.0.0.1:$VNC_PORT, password $VNC_PASSWORD)"
    if [ "$(uname)" = Darwin ]; then
        open "$url"
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" >/dev/null 2>&1 &
    fi
}
