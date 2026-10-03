# -*- coding: utf-8 -*-
"""
snippet_single_effect.py - Minimal snippet to trigger a single haptic effect
via the hapticd daemon.

Usage:
  Copy the lines below into any script. Adjust `channel` and `effect` as needed.
  No extra dependencies or functions required.

  The hapticd daemon must be running and the socket at /run/hapticd.sock
  must be accessible.
"""
import socket

# --- Configuration ---
channel = 0              # MUX channel(s): 0-3, combination (e.g. 0+2), or "all"
# channel = "0+2"        # e.g. broadcast to channels 0 and 2 simultaneously
effect = "double_click"  # Effect name (e.g. "alert") or integer (e.g. 47)

# --- Send command to hapticd ---
sock = socket.socket(socket.AF_UNIX, socket.SOCK_STREAM)
sock.connect("/run/hapticd.sock")
sock.sendall(f"{channel} {effect}\n".encode("utf-8"))
response = sock.recv(1024).decode("utf-8").strip()
sock.close()

if response.startswith("ERROR"):
    print("Failed:", response)
else:
    print("OK:", response)
