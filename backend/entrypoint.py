#!/usr/bin/env python3
"""Prepare Railway's mounted data volume, then drop privileges before serving."""
import os
import sys

DATA_DIR = os.environ.get("JASSIM_DATA_DIR", "/data")
os.makedirs(DATA_DIR, exist_ok=True)
try:
    os.chown(DATA_DIR, 10001, 10001)
except PermissionError:
    # A platform-managed volume may disallow ownership changes. Fail clearly
    # rather than starting a server that cannot persist its database.
    raise SystemExit("JASSIM_DATA_DIR is not writable by the application user")
os.setgid(10001)
os.setuid(10001)
os.execv(sys.executable, [sys.executable, "/app/server.py"])
