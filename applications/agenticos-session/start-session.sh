#!/usr/bin/env bash
set -euo pipefail

# AgenticOS graphical session launched by LightDM.
# LightDM owns Xorg, authentication, VT switching, and DISPLAY.
# This script owns only the user's desktop session.

export PATH="/usr/local/bin:/usr/bin:/bin"
export XDG_CURRENT_DESKTOP="AgenticOS"
export XDG_SESSION_DESKTOP="AgenticOS"
export DESKTOP_SESSION="agenticos"

# Start the Openbox window manager.
if command -v openbox-session >/dev/null 2>&1; then
    openbox-session &
else
    openbox &
fi

OPENBOX_PID=$!

# Give Openbox a moment to initialise the root window.
sleep 1

# Set AgenticOS deep dark background color on the root X11 window.
if command -v xsetroot >/dev/null 2>&1; then
    xsetroot -solid "#030712" || true
fi

# Start the native AgenticOS desktop shell.
exec /usr/bin/python3 /opt/agenticos/applications/agenticos-shell/main.py
