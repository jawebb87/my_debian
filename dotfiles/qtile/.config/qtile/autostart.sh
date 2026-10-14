#!/usr/bin/env bash

# Terminate any running instances to avoid duplicates
pkill -u $UID -x picom 2>/dev/null || true
pkill -u $UID -x dunst 2>/dev/null || true

# Wait until the processes have shut down
while pgrep -u $UID -x picom >/dev/null; do sleep 0.1; done
while pgrep -u $UID -x dunst >/dev/null; do sleep 0.1; done

# 1. Start notification daemon (Dunst)
if command -v dunst >/dev/null 2>&1; then
    dunst &
fi

# 2. Start compositor (Picom)
if command -v picom >/dev/null 2>&1; then
    picom -b --config ~/.config/picom/picom.conf
fi

# 3. Start Polkit agent (if installed)
for agent in \
    /usr/lib/policykit-1-gnome/polkit-gnome-authentication-agent-1 \
    /usr/libexec/polkit-gnome-authentication-agent-1 \
    /usr/bin/lxpolkit; do
    if [ -f "$agent" ]; then
        "$agent" &
        break
    fi
done

# 4. Start XDG Desktop Portals (Firefox & GTK dark/light appearance integration)
systemctl --user start xdg-desktop-portal xdg-desktop-portal-gtk 2>/dev/null || true

