#!/usr/bin/env python3
"""Entry point: python3 run_server.py [--port 8000]"""

from __future__ import annotations

import os
import sys

if __name__ == "__main__":
    port = None
    args = sys.argv[1:]
    for i, arg in enumerate(args):
        if arg == "--port" and i + 1 < len(args):
            port = args[i + 1]
    if port:
        os.environ["BLXVERSE_PORT"] = port
    from blxverse.server import main
    main()
