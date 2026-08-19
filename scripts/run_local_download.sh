#!/bin/zsh
set -eu

PROJECT_DIR="/Users/chris/.codex/visualizations/2026/07/26/019f9c96-5bf4-7113-a35b-886ab1e2de05/periodicals-r2-sync"
cd "$PROJECT_DIR"

python3 scripts/download_to_vault.py --config periodicals.json --recent 2

