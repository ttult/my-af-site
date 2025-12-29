#!/bin/bash
set -e

HUGO_VERSION="0.146.0"
TMP_DIR="$(mktemp -d)"

echo "=== Hugo install (v${HUGO_VERSION} extended) ==="

if ! command -v hugo >/dev/null; then
  echo "Installing Hugo..."
  wget -q -O "${TMP_DIR}/hugo.tar.gz" \
    "https://github.com/gohugoio/hugo/releases/download/v${HUGO_VERSION}/hugo_extended_${HUGO_VERSION}_Linux-64bit.tar.gz"

  tar -xzf "${TMP_DIR}/hugo.tar.gz" -C "${TMP_DIR}"
  sudo mv "${TMP_DIR}/hugo" /usr/local/bin/hugo
else
  echo "Hugo already installed:"
  hugo version
fi

rm -rf "${TMP_DIR}"

echo "=== Git submodule update (PaperMod) ==="
git submodule update --init --recursive

echo "=== Python dependencies ==="
python3 -m pip install --upgrade pip
pip install -r requirements.txt

echo "=== Playwright ==="
playwright install
playwright install-deps
