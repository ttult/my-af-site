#!/bin/bash
set -e

echo "=== Hugo install ==="
if ! command -v hugo >/dev/null; then
  wget -q https://github.com/gohugoio/hugo/releases/download/v0.120.4/hugo_extended_0.120.4_Linux-64bit.tar.gz
  tar -xzf hugo_extended_0.120.4_Linux-64bit.tar.gz
  sudo mv hugo /usr/local/bin/
  rm hugo_extended_0.120.4_Linux-64bit.tar.gz
fi

echo "=== Git submodule ==="
git submodule update --init --recursive

echo "=== Python deps ==="
pip install --upgrade pip
pip install -r requirements.txt

echo "=== Playwright ==="
playwright install
playwright install-deps
