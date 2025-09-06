#!/bin/bash

# WayKeyLight Runner Script
# Activates virtual environment and launches the application

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
VENV_DIR="$SCRIPT_DIR/venv"
APP_SCRIPT="$SCRIPT_DIR/waykeylight.py"

# Check if virtual environment exists
if [ ! -d "$VENV_DIR" ]; then
    echo "Virtual environment not found!"
    echo "Please run ./setup.sh first"
    exit 1
fi

# Check if app script exists
if [ ! -f "$APP_SCRIPT" ]; then
    echo "Application script not found!"
    exit 1
fi

# Activate virtual environment and run the app
"$VENV_DIR/bin/python" "$APP_SCRIPT" "$@"