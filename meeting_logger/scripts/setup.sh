#!/usr/bin/env bash
set -euo pipefail

python3 -m venv venv
source venv/bin/activate

python -m pip install --upgrade pip
python -m pip install -r requirements.txt

echo "If ffmpeg is missing, install with: sudo apt install ffmpeg -y"
