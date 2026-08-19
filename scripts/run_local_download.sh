#!/bin/zsh
set -eu

PROJECT_DIR="/Users/chris/.codex/visualizations/2026/07/26/019f9c96-5bf4-7113-a35b-886ab1e2de05/periodicals-r2-sync"
cd "$PROJECT_DIR"

python3 scripts/download_originals_to_library.py --config periodicals.json --recent 6
python3 scripts/generate_issue_indexes.py --config periodicals.json --recent 6
