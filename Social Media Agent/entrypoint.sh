#!/usr/bin/env bash
# Starts a virtual screen and a web viewer for it, then runs the container command.
# The viewer is how a user sees the Agent Reach browser window to log in to a site.
set -euo pipefail

readonly SCREEN_SIZE="${SCREEN_SIZE:-1280x800x24}"
readonly VIEWER_PORT="${VIEWER_PORT:-6080}"
readonly VNC_PORT=5900
readonly DISPLAY_SOCKET="/tmp/.X11-unix/X${DISPLAY#:}"
readonly SCREEN_START_TIMEOUT_SECONDS=10

# A restarted container keeps /tmp; stale files would stop Xvfb from starting.
rm -f "/tmp/.X${DISPLAY#:}-lock" "$DISPLAY_SOCKET"
# A recreated container has a new hostname; Chrome's leftover profile locks would block it.
rm -f "$HOME"/.agent-reach/browser/profile/Singleton{Lock,Cookie,Socket}
Xvfb "$DISPLAY" -screen 0 "$SCREEN_SIZE" -nolisten tcp &

for _ in $(seq "$SCREEN_START_TIMEOUT_SECONDS"); do
	[[ -S "$DISPLAY_SOCKET" ]] && break
	sleep 1
done
if [[ ! -S "$DISPLAY_SOCKET" ]]; then
	echo "Virtual screen $DISPLAY did not start within ${SCREEN_START_TIMEOUT_SECONDS}s" >&2
	exit 1
fi

# VNC listens only inside the container; the web viewer is the single published entry point.
x11vnc -display "$DISPLAY" -rfbport "$VNC_PORT" -localhost -forever -shared -nopw -quiet &
websockify --web /usr/share/novnc "$VIEWER_PORT" "localhost:$VNC_PORT" &

exec "$@"
