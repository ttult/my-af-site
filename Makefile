# ============================
# Ultimate ROOM Makefile
# ============================

.DEFAULT_GOAL := help

HUGO_ENV ?= development
HUGO_PORT ?= 1313

# ----------------------------
# Commands
# ----------------------------

help:
	@echo ""
	@echo "Usage:"
	@echo "  make init        初期セットアップ（build.sh実行）"
	@echo "  make server      Hugo 開発サーバー起動"
	@echo "  make build       本番ビルド"
	@echo "  make clean       生成物削除"
	@echo ""

init:
	@echo ">>> Initializing environment..."
	@chmod +x build.sh
	@./build.sh

server:
	@echo ">>> Starting Hugo server..."
	@hugo server -D --bind 0.0.0.0 --port $(HUGO_PORT)

build:
	@echo ">>> Building site (production)..."
	@HUGO_ENV=production hugo --minify

clean:
	@echo ">>> Cleaning generated files..."
	@rm -rf public resources
