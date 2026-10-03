#!/usr/bin/env bash
#
# uninstall_hapticd.sh - Uninstall the hapticd system service and CLI.
#
# Reverses install_hapticd.sh: stops and disables the hapticd service, removes
# the systemd unit, the haptic-cli client and the /opt/hapticd directory.
# Requires sudo; the password is prompted interactively.
set -euo pipefail

UNIT_NAME="hapticd"
UNIT_FILE="/etc/systemd/system/hapticd.service"
CLI_PATH="/usr/local/bin/haptic-cli"
DEST_DIR="/opt/hapticd"

echo "== hapticd system service uninstaller =="

# --- sudo password prompt (credentials cached for the rest of the script) ---
if [[ "$EUID" -eq 0 ]]; then
    echo "[OK] Running as root."
else
    echo "Requesting sudo privileges (password prompt)..."
    sudo -v
    echo "[OK] sudo credentials accepted."
fi

# --- confirmation ---
read -r -p "Remove hapticd service, CLI and /opt/hapticd? [y/N] " confirm
[[ "$confirm" =~ ^[Yy]$ ]] || { echo "Aborted."; exit 0; }

# --- stop, disable and remove the systemd unit ---
if [[ -f "$UNIT_FILE" ]]; then
    echo "Stopping service $UNIT_NAME ..."
    sudo systemctl stop "$UNIT_NAME" || true
    echo "Disabling service $UNIT_NAME ..."
    sudo systemctl disable "$UNIT_NAME" || true
    echo "Removing systemd unit ..."
    sudo rm -f "$UNIT_FILE"
    echo "Reloading systemd ..."
    sudo systemctl daemon-reload
    echo "[OK] service removed."
else
    echo "[SKIP] service unit not installed."
fi

# --- remove the CLI ---
if [[ -f "$CLI_PATH" ]]; then
    echo "Removing CLI ..."
    sudo rm -f "$CLI_PATH"
    echo "[OK] CLI removed."
else
    echo "[SKIP] CLI not installed."
fi

# --- remove the daemon directory (guard: only if it contains hapticd.py) ---
if [[ -f "$DEST_DIR/hapticd.py" ]]; then
    echo "Removing $DEST_DIR ..."
    sudo rm -rf "$DEST_DIR"
    echo "[OK] daemon directory removed."
else
    echo "[SKIP] $DEST_DIR not present or no hapticd.py marker."
fi

echo "[OK] Done. hapticd uninstalled (project files untouched)."
