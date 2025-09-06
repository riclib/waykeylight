#!/bin/bash

# WayKeyLight Setup Script
# Creates virtual environment and installs dependencies

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"

echo "==================================="
echo "WayKeyLight Setup"
echo "==================================="

# Check if Python 3 is installed
if ! command -v python3 &> /dev/null; then
    echo "Error: Python 3 is not installed"
    exit 1
fi

# Remove old venv if it exists
if [ -d "$VENV_DIR" ]; then
    echo "Removing existing virtual environment..."
    rm -rf "$VENV_DIR"
fi

# Create virtual environment
echo "Creating virtual environment..."
python3 -m venv "$VENV_DIR"

# Activate virtual environment
echo "Activating virtual environment..."
source "$VENV_DIR/bin/activate"

# Upgrade pip
echo "Upgrading pip..."
pip install --upgrade pip

# Install requirements
echo "Installing dependencies..."
pip install -r "$SCRIPT_DIR/requirements.txt"

# Make scripts executable
chmod +x "$SCRIPT_DIR/waykeylight.py"
chmod +x "$SCRIPT_DIR/run.sh"

echo ""
echo "==================================="
echo "Setup complete!"
echo "==================================="
echo ""
echo "To run WayKeyLight:"
echo "  ./run.sh"
echo ""
echo "To install as system service:"
echo "  make install"
echo ""
echo "To add to autostart:"
echo "  Add this to your Hyprland config:"
echo "  exec-once = $SCRIPT_DIR/run.sh"