# Sourced (not executed) by the run-*.sh scripts in linux-build/ and
# windows-build/: run AYAB in a container of the image built from
# docker/Dockerfile, whose display is served over VNC (see
# docker/image/start-vnc-display), and open a VNC viewer on it (TigerVNC if
# installed, otherwise macOS Screen Sharing).
#
# Environment: VNC_PORT (default 5901), VNC_PASSWORD (default ayab),
#              CONTAINER_NAME (default ayab), DARK_MODE (default 0; 1 for
#              dark mode)

: "${VNC_PORT:=5901}"
: "${VNC_PASSWORD:=ayab}"
: "${CONTAINER_NAME:=ayab}"
repo=$(cd "$(dirname "$0")/.." && pwd)

passwd_file=
trap '[ -z "$passwd_file" ] || rm -f "$passwd_file"' EXIT

image=ayab

# Build the image (quick when nothing changed)
build_image() {
    echo "Building $image image..."
    docker build --quiet --platform linux/amd64 \
        --file "$repo/docker/Dockerfile" \
        --target runner \
        --tag "$image" \
        "$repo" >/dev/null
}

container_running() {
    docker ps --quiet --filter "name=^$CONTAINER_NAME\$" | grep -q .
}

# run_in_vnc DESCRIPTION [docker run options...] IMAGE [command...]
run_in_vnc() {
    description=$1
    shift

    docker rm --force "$CONTAINER_NAME" >/dev/null 2>&1 || true

    echo "Starting $description in container $CONTAINER_NAME..."
    docker run --detach --rm --platform linux/amd64 \
        --name "$CONTAINER_NAME" \
        --publish "127.0.0.1:$VNC_PORT:5900" \
        --env VNC_PASSWORD="$VNC_PASSWORD" \
        --env DARK_MODE="${DARK_MODE:-0}" \
        "$@" >/dev/null

    # x11vnc prints its port once it accepts connections
    until docker logs "$CONTAINER_NAME" 2>&1 | grep -q '^PORT='; do
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
            'xwininfo -root -tree -display "${DISPLAY:-:99}" | grep -q "\"AYAB"' 2>/dev/null; do
        if ! container_running; then
            echo "Container exited before AYAB started:" >&2
            docker logs "$CONTAINER_NAME" 2>&1 | tail -n 20 >&2 || true
            exit 1
        fi
        sleep 2
    done

    open_viewer

    echo "Following logs; press Ctrl-C to stop the container."
    trap 'docker stop "$CONTAINER_NAME" >/dev/null 2>&1; exit 0' INT TERM
    docker logs --follow "$CONTAINER_NAME" 2>&1 | grep -vE 'x11vnc|^[0-9]{2}/[0-9]{2}/[0-9]{4} ' &
    wait
}

open_viewer() {
    # TigerVNC reads the password from a standard VNC password file
    passwd_file=$(mktemp -t ayab-vncpasswd)
    docker exec "$CONTAINER_NAME" sh -c \
        'x11vnc -storepasswd "$VNC_PASSWORD" /tmp/vncpasswd >/dev/null 2>&1 && cat /tmp/vncpasswd' \
        > "$passwd_file"

    tigervnc_app=$(ls -d /Applications/TigerVNC*.app "$HOME"/Applications/TigerVNC*.app 2>/dev/null | tail -n 1 || true)
    if command -v vncviewer >/dev/null 2>&1; then
        echo "Opening vncviewer"
        vncviewer -passwd "$passwd_file" "127.0.0.1::$VNC_PORT" >/dev/null 2>&1 &
    elif [ -n "$tigervnc_app" ]; then
        echo "Opening $(basename "$tigervnc_app")"
        open -n -a "$tigervnc_app" --args -passwd "$passwd_file" "127.0.0.1::$VNC_PORT"
    else
        echo "Opening Screen Sharing"
        open "vnc://:$VNC_PASSWORD@127.0.0.1:$VNC_PORT"
    fi
}
