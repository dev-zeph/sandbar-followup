#!/bin/bash
# Double-click to run the Sandbar show follow-up. Nothing is ever sent.
cd "$(dirname "$0")"
echo "Sandbar show follow-up"
echo
.venv/bin/python sandbar.py
echo
read -p "Done. Press Enter to close this window."
