#!/usr/bin/env bash
# Re-render every .mmd to .svg in light mode. Idempotent.
#
# Requirements:
#   - Node 18+
#   - npx @mermaid-js/mermaid-cli (auto-downloads Chrome via Puppeteer)
#
# Notes on light mode:
#   - We force theme=default (Mermaid's built-in light theme) and a white
#     background, regardless of the viewer's color scheme.
#   - Custom palette lives in .mermaid-config.json next to this script.

set -euo pipefail
cd "$(dirname "$0")"

PUPPETEER_CFG="$(mktemp)"
trap 'rm -f "$PUPPETEER_CFG"' EXIT
cat > "$PUPPETEER_CFG" <<'JSON'
{ "args": ["--no-sandbox", "--disable-setuid-sandbox"] }
JSON

shopt -s nullglob
mmdc=(npx --yes "@mermaid-js/mermaid-cli")
count=0
for src in *.mmd; do
  out="${src%.mmd}.svg"
  echo "rendering $src -> $out"
  "${mmdc[@]}" \
    --input "$src" \
    --output "$out" \
    --theme default \
    --backgroundColor "#ffffff" \
    --configFile .mermaid-config.json \
    --puppeteerConfigFile "$PUPPETEER_CFG" \
    >/dev/null
  count=$((count + 1))
done
echo "done: $count SVGs in $(pwd)"
