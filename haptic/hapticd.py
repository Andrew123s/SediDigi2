#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
hapticd.py - Haptic Feedback Daemon for TM6605 Driver via PCA9548A

Installation:
  Target directory:  /opt/hapticd/hapticd.py
  Permissions:       chmod 755 hapticd.py
  Owner:             root:root
  Socket path:       /run/hapticd.sock (created by the daemon)
  Socket permissions: chmod 666 /run/hapticd.sock (optional, for non-root clients)

  Note: Root privileges required for I2C bus access (/dev/i2c-1).
  Manual start: sudo python3 /opt/hapticd/hapticd.py
  systemd start: copy hapticd.service to /etc/systemd/system/

Protocol:
  Client sends:   <channel> <effect>
  channel:        0-3 (MUX channel), combination (e.g. 0+2) or all
                  ('all' and combinations are broadcast simultaneously)
  effect:         Enum name (e.g. double_click), integer (e.g. 10)
                  or sequence name (e.g. short_long)
  Response:       OK\n  or  ERROR: <message>\n

Examples:
  echo "0 double_click" | socat - UNIX-CONNECT:/run/hapticd.sock
  echo "0+2 47" | socat - UNIX-CONNECT:/run/hapticd.sock
  echo "all 47" | socat - UNIX-CONNECT:/run/hapticd.sock
"""
import socket
import os
import sys
import signal
import logging

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from DFRobot_TM6605 import DFRobot_TM6605, EFFECT_SEQUENCES
from PCA9548A import PCA9548A

SOCKET_PATH = "/run/hapticd.sock"
LOG_FORMAT = "%(asctime)s [%(levelname)s] %(message)s"
MUX_BUS = 1
MUX_ADDRESS = 0x70
CHANNEL_LIST = [0, 1, 2, 3]

logging.basicConfig(
    level=logging.INFO,
    format=LOG_FORMAT,
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("hapticd")


class HapticDaemon:
    """Manages TM6605 driver instances via PCA9548A multiplexer."""

    def __init__(self):
        self.mux = None
        self.drivers = {}
        self.sock = None
        self.running = False
        signal.signal(signal.SIGTERM, self._handle_signal)
        signal.signal(signal.SIGINT, self._handle_signal)

    def _handle_signal(self, signum, frame):
        logger.info("Shutdown signal %d received", signum)
        self.running = False

    def init_drivers(self):
        """Initialize TM6605 drivers for all configured MUX channels."""
        self.mux = PCA9548A(bus=MUX_BUS, address=MUX_ADDRESS)
        logger.info("PCA9548A initialized on bus %d (address 0x%02x)", MUX_BUS, MUX_ADDRESS)
        for ch in CHANNEL_LIST:
            try:
                self.mux.select_channel(ch)
                driver = DFRobot_TM6605(bus=MUX_BUS)
                if driver.begin() != 0:
                    logger.warning("TM6605 not found on channel %d", ch)
                    continue
                self.drivers[ch] = driver
                logger.info("TM6605 initialized on channel %d", ch)
            except Exception as e:
                logger.error("Error on channel %d: %s", ch, e)

        if not self.drivers:
            raise RuntimeError("No TM6605 device found")

    def _resolve_effect(self, effect_str):
        """Convert effect string (name, sequence name or number) to a list of values."""
        if effect_str in EFFECT_SEQUENCES:
            return [e.value for e in EFFECT_SEQUENCES[effect_str]]

        try:
            effect_value = int(effect_str)
            valid_values = [e.value for e in DFRobot_TM6605.Effect]
            if effect_value not in valid_values:
                raise ValueError("Invalid effect value: {}".format(effect_value))
            return [effect_value]
        except ValueError:
            try:
                effect_enum = DFRobot_TM6605.Effect[effect_str]
                return [effect_enum.value]
            except KeyError:
                valid_names = [e.name for e in DFRobot_TM6605.Effect]
                raise ValueError(
                    "Unknown effect '{}'. Valid: {}. Sequences: {}".format(
                        effect_str, ", ".join(valid_names), ", ".join(EFFECT_SEQUENCES.keys())
                    )
                )

    def _parse_command(self, data):
        """Parse client command. Returns (channel_list, effect_value)."""
        parts = data.strip().split()
        if len(parts) != 2:
            raise ValueError(
                "Invalid format. Expected: <channel> <effect>, e.g. '0 double_click'"
            )

        ch_arg = parts[0].lower()
        if ch_arg == "all":
            channels = sorted(self.drivers.keys())
        else:
            channels = []
            for part in ch_arg.split("+"):
                ch = int(part)
                if ch not in self.drivers:
                    raise ValueError("Channel {} not available".format(ch))
                channels.append(ch)
            channels = sorted(set(channels))

        effect_value = self._resolve_effect(parts[1])
        return channels, effect_value

    def _play_effect(self, channels, effect_values):
        """Play effect(s) simultaneously on the specified channels via MUX broadcast.

        A single write to 0x2D reaches every module whose channel is included
        in the MUX channel mask, so all selected channels trigger at once.
        """
        mask = 0
        for ch in channels:
            mask |= (1 << ch)
        self.mux.select_channels(mask)
        self.drivers[channels[0]].play_sequence(effect_values)
        self.mux.deselect()
        logger.info("Effects %s started on channels %s", effect_values, channels)

    def _handle_client(self, conn):
        """Handle a single client connection."""
        try:
            data = b""
            while True:
                chunk = conn.recv(1024)
                if not chunk:
                    break
                data += chunk
                if b"\n" in data:
                    break

            if not data:
                return

            command = data.decode("utf-8").strip()
            logger.info("Command received: %s", command)

            channels, effect_value = self._parse_command(command)
            self._play_effect(channels, effect_value)

            conn.sendall(b"OK\n")
        except Exception as e:
            logger.error("Error executing command: %s", e)
            conn.sendall("ERROR: {}\n".format(e).encode("utf-8"))
        finally:
            conn.close()

    def start(self):
        """Start the daemon."""
        logger.info("Starting hapticd")
        self.init_drivers()

        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)

        self.sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        self.sock.bind(SOCKET_PATH)
        self.sock.listen(5)
        os.chmod(SOCKET_PATH, 0o666)

        logger.info("Socket created: %s", SOCKET_PATH)
        self.running = True

        while self.running:
            try:
                self.sock.settimeout(1.0)
                try:
                    conn, _ = self.sock.accept()
                    self._handle_client(conn)
                except socket.timeout:
                    continue
            except Exception as e:
                if self.running:
                    logger.error("Socket error: %s", e)

        self._cleanup()

    def _cleanup(self):
        """Clean up resources on shutdown."""
        logger.info("Shutting down")
        if self.sock:
            self.sock.close()
        if os.path.exists(SOCKET_PATH):
            os.unlink(SOCKET_PATH)
        logger.info("hapticd stopped")


def main():
    daemon = HapticDaemon()
    try:
        daemon.start()
    except Exception as e:
        logger.critical("Startup failed: %s", e)
        sys.exit(1)


if __name__ == "__main__":
    main()
