#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "$0")"
if [[ ! -x .venv/bin/python ]]; then
  echo 'Chưa có môi trường .venv. Xem các lệnh cài đặt trong README.md.'
  exit 1
fi
exec .venv/bin/python main.py
