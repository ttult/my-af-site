#!/bin/bash

# Codespacesのポート番号とドメイン名を元にbaseURLを生成
CODESPACE_URL="https://$CODESPACE_NAME-1313.app.github.dev/"

# Hugoサーバーを起動
hugo server -D --bind=0.0.0.0 --baseURL="$CODESPACE_URL"