# -*- coding: utf-8 -*-
"""
snippet_effect_sequence.py - Minimal snippet to trigger a sequence of haptic
effects via the hapticd daemon.

Usage:
  Copy the lines below into any script. Adjust `channel` and `sequence` as needed.
  No extra dependencies or functions required.

  The hapticd daemon must be running and the socket at /run/hapticd.sock
  must be accessible.

  Sequence names are defined in EFFECT_SEQUENCES (DFRobot_TM6605.py) and are
  resolved by the daemon, e.g. "short_long" plays effect 1 + 70 in sequence.
"""
import socket

# --- Configuration ---
channel = 0              # MUX channel(s): 0-3, combination (e.g. 0+2), or "all"
# channel = "0+2"        # e.g. broadcast sequence to channels 0 and 2 simultaneously
sequence = "short_long"  # Sequence name (see EFFECT_SEQUENCES), e.g. "short_long"

# --- Send command to hapticd ---
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/run/hapticd.sock")
sock.sendall(f"{channel} {sequence}\n".encode("utf-8"))
response = sock.recv(1024).decode("utf-8").strip()
sock.close()

if response.startswith("ERROR"):
    print("Failed:", response)
else:
    print("OK:", response)
