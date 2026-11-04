#!/usr/bin/env bash
set -euo pipefail

echo "==> Configuring Musegix Cloud Environment on Docker Sandboxes..."
mkdir -p /workspace/Musegix
cd /workspace/Musegix

# Update packages and install prerequisites
apt-get update -qq && apt-get install -y -qq \
    git curl build-essential cmake ninja-build python3-pip python3-venv \
    pkg-config libsqlite3-dev

# Set up virtual environment
python3 -m venv /workspace/venv
source /workspace/venv/bin/activate
pip install --upgrade pip

# Install requirements
if [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
fi

echo "==> Cloud Environment successfully provisioned."

