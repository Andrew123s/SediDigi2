#!/usr/bin/env bash
#
# install_hapticd.sh - Install the hapticd daemon as a system service.
#
# Installs DFRobot_TM6605.py, PCA9548A.py and hapticd.py to /opt/hapticd,
# installs the hapticd systemd unit and the haptic-cli client to /usr/local/bin.
# Requires sudo; the password is prompted interactively.
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEST_DIR="/opt/hapticd"
UNIT_NAME="hapticd"
CLI_NAME="haptic-cli"
FILES=(DFRobot_TM6605.py PCA9548A.py hapticd.py)
UNIT_FILE="hapticd.service"
CLI_FILE="haptic_cli.py"

echo "== hapticd system service installer =="

# --- sudo password prompt (credentials cached for the rest of the script) ---
if [[ "$EUID" -eq 0 ]]; then
    echo "[OK] Running as root."
else
    echo "Requesting sudo privileges (password prompt)..."
    sudo -v
    echo "[OK] sudo credentials accepted."
fi

# --- sanity checks ---
for f in "${FILES[@]}" "$UNIT_FILE" "$CLI_FILE"; do
    if [[ ! -f "$SCRIPT_DIR/$f" ]]; then
        echo "[ERROR] $f not found next to this script." >&2
        exit 1
    fi
done
if ! command -v python3 >/dev/null 2>&1; then
    echo "[ERROR] python3 not found." >&2
    exit 1
fi

# --- daemon files ---
echo "Installing daemon files to $DEST_DIR ..."
sudo install -d -o root -g root -m 755 "$DEST_DIR"
sudo install -m 644 -o root -g root "$SCRIPT_DIR/DFRobot_TM6605.py" "$DEST_DIR/"
sudo install -m 644 -o root -g root "$SCRIPT_DIR/PCA9548A.py" "$DEST_DIR/"
sudo install -m 755 -o root -g root "$SCRIPT_DIR/hapticd.py" "$DEST_DIR/"
echo "[OK] daemon files installed."

# --- CLI ---
echo "Installing CLI as /usr/local/bin/$CLI_NAME ..."
sudo install -m 755 -o root -g root "$SCRIPT_DIR/$CLI_FILE" "/usr/local/bin/$CLI_NAME"
echo "[OK] CLI installed."

# --- systemd unit ---
echo "Installing systemd unit ..."
sudo install -m 644 -o root -g root "$SCRIPT_DIR/$UNIT_FILE" "/etc/systemd/system/$UNIT_NAME.service"
echo "[OK] systemd unit installed."

# --- enable and start ---
echo "Reloading systemd ..."
sudo systemctl daemon-reload
echo "[OK] systemd reloaded."

echo "Enabling service $UNIT_NAME ..."
sudo systemctl enable "$UNIT_NAME"
echo "[OK] service enabled."

echo "Starting service $UNIT_NAME ..."
sudo systemctl restart "$UNIT_NAME"
echo "[OK] service started."

# --- verification ---
if systemctl is-active --quiet "$UNIT_NAME"; then
    echo "[OK] Done. Service '$UNIT_NAME' is active and enabled."
else
    echo "[ERROR] Service '$UNIT_NAME' failed to start." >&2
    systemctl status "$UNIT_NAME" --no-pager || true
    exit 1
fi

systemctl status "$UNIT_NAME" --no-pager

echo
echo "Next steps:"
echo "  haptic-cli --list"
echo "  haptic-cli --channel 0 --effect short_long"
