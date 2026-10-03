#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
haptic_cli.py - CLI Client for the hapticd Daemon

Installation:
  Target directory:  /usr/local/bin/haptic-cli
  Permissions:       chmod 755 haptic-cli
  Owner:             root:root

  Alternative: Leave as haptic_cli.py and run with
  `python3 haptic_cli.py`.

  Note: The user must have read/write access to the socket
  /run/hapticd.sock (set to chmod 666 by the daemon).

  Requires DFRobot_TM6605.py (single source of truth for the effect
  list). When deployed as /usr/local/bin/haptic-cli, the module is
  looked up in /opt/hapticd; when run from the project directory,
  the local copy takes precedence.

Usage:
  haptic-cli --channel <0|1|2|3|0+2|all> --effect <name|number>
  haptic-cli --channel 0 --effect double_click
  haptic-cli --channel 0+2 --effect 47
  haptic-cli --channel all --effect 47
  haptic-cli --list   (lists all available effects)
"""
import socket
import sys
import os
import argparse

SOCKET_PATH = "/run/hapticd.sock"

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, "/opt/hapticd")
from DFRobot_TM6605 import DFRobot_TM6605, EFFECT_SEQUENCES

EFFECTS = {e.name: e.value for e in DFRobot_TM6605.Effect}
SEQUENCES = {name: [e.value for e in effects] for name, effects in EFFECT_SEQUENCES.items()}


def channel_arg(value):
    """Validate the --channel argument: 0-3, '+' combinations, or 'all'."""
    if value.lower() == "all":
        return value
    parts = value.split("+")
    if not parts or any(p not in ("0", "1", "2", "3") for p in parts):
        raise argparse.ArgumentTypeError(
            "channel must be 0-3, a combination like 0+2, or 'all'"
        )
    return value


def list_effects():
    """Print all available effects and sequences to stdout."""
    print("Available effects:")
    for name, value in sorted(EFFECTS.items(), key=lambda x: x[1]):
        print("  {:40s} {:>3d}".format(name, value))
    if SEQUENCES:
        print()
        print("Sequences:")
        for name, values in sorted(SEQUENCES.items()):
            print("  {:40s} {}".format(name, " -> ".join(str(v) for v in values)))


def send_command(channel, effect):
    """Send a command to the hapticd daemon via Unix Domain Socket."""
    command = "{} {}\n".format(channel, effect)
    try:
        sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
        sock.connect(SOCKET_PATH)
        sock.sendall(command.encode("utf-8"))
        response = sock.recv(1024).decode("utf-8").strip()
        sock.close()
        print(response)
        if response.startswith("ERROR"):
            sys.exit(1)
    except FileNotFoundError:
        print("ERROR: Socket not found. Is hapticd running?")
        sys.exit(1)
    except ConnectionRefusedError:
        print("ERROR: Connection to daemon failed.")
        sys.exit(1)


def main():
    parser = argparse.ArgumentParser(
        description="CLI client for the hapticd Haptic Feedback Daemon"
    )
    parser.add_argument(
        "--channel",
        type=channel_arg,
        help="MUX channel(s): 0-3, a combination like 0+2, or all"
    )
    parser.add_argument(
        "--effect",
        help="Effect name (e.g. double_click) or number (e.g. 10)"
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="List all available effects"
    )

    args = parser.parse_args()

    if getattr(args, "list"):
        list_effects()
        return

    if not args.channel or not args.effect:
        parser.print_help()
        sys.exit(1)

    send_command(args.channel, args.effect)


if __name__ == "__main__":
    main()
