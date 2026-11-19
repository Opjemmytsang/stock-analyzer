#!/usr/bin/env bash
set -euo pipefail
mkdir -p ml/data
for year in 2022 2023 2024 2025 2026; do
  for side in bid ask; do
    echo "Downloading XAUUSD ${year} ${side}"
    npx --yes dukascopy-node -i xauusd -from "${year}-01-01" -to "$((year+1))-01-01" -t m15 -p "${side}" -f csv -dir ml/data -fn "xauusd_m15_${side}_${year}" --cache --retries 3 --batch-pause 1000
  done
done
