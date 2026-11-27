#!/usr/bin/env bash
# Зависимости для сборки роликов (Ubuntu). Playwright/Chromium и ffmpeg уже есть в облачной среде Claude Code.
set -e
python3 -c "import scipy, numpy, PIL" 2>/dev/null || pip install -q scipy numpy pillow
command -v ffmpeg >/dev/null || echo "Нужен ffmpeg"
node -e "require('playwright')" 2>/dev/null || echo "Нужен playwright (npm i playwright && npx playwright install chromium)"
echo "setup ok"
