#!/usr/bin/env bash
set -euo pipefail

HUGO_VERSION="0.120.4"
HUGO_BIN="/usr/local/bin/hugo"

echo "======================================"
echo " Ultimate ROOM - build.sh"
echo "======================================"

#######################################
# Hugo install (clean & safe)
#######################################
echo ">>> Checking Hugo..."

if ! command -v hugo >/dev/null 2>&1; then
  echo ">>> Installing Hugo Extended v${HUGO_VERSION}"

  TMP_DIR="$(mktemp -d)"
  trap 'rm -rf "$TMP_DIR"' EXIT

  curl -sL \
    "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_Linux-64bit.tar.gz" \
    -o "${TMP_DIR}/hugo.tar.gz"

  tar -xzf "${TMP_DIR}/hugo.tar.gz" -C "${TMP_DIR}" hugo
  sudo mv "${TMP_DIR}/hugo" "${HUGO_BIN}"
  sudo chmod +x "${HUGO_BIN}"

  echo ">>> Hugo installed at ${HUGO_BIN}"
else
  echo ">>> Hugo already installed: $(hugo version)"
fi

#######################################
# Git submodule
#######################################
echo ">>> Updating git submodules..."
git submodule update --init --recursive

#######################################
# Python dependencies
#######################################
if [ -f "requirements.txt" ]; then
  echo ">>> Installing Python dependencies..."
  python -m pip install --upgrade pip
  pip install -r requirements.txt
else
  echo ">>> requirements.txt not found, skipping Python deps"
fi

#######################################
# Playwright
#######################################
if command -v playwright >/dev/null 2>&1; then
  echo ">>> Installing Playwright browsers..."
  playwright install
  playwright install-deps
else
  echo ">>> Playwright not found, skipping"
fi

echo "======================================"
echo " Build completed successfully ✔"
echo "======================================"
