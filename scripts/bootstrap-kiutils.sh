#!/bin/bash
set -e

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
WORKSPACE_ROOT=/workspace/hephaistus
VENV_PATH="$WORKSPACE_ROOT/.venv"

echo "Bootstrapping KiUtils in workspace venv at $VENV_PATH"

if [ -d "$VENV_PATH" ]; then
  echo "Virtualenv already exists. Skipping creation."
else
  python3 -m venv "$VENV_PATH"
fi

source "$VENV_PATH/bin/activate"
python -m pip install --upgrade pip
python -m pip install kiutils

echo "KiUtils environment ready."
