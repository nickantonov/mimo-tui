#!/bin/bash
echo "==============================="
echo " MiMo TUI v1.0 - Install"
echo "==============================="
echo ""
echo "Installing dependencies..."
pip3 install -r requirements.txt || python3 -m pip install -r requirements.txt || echo "ERROR: pip not found. Install python3-pip first."
echo ""
echo "Done! Run './run.sh' to start."
