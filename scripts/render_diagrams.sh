#!/usr/bin/env bash
# Render every Mermaid source in docs/diagrams to PNG and SVG.
# Requires: npm install -g @mermaid-js/mermaid-cli
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="$ROOT/docs/diagrams"
OUT="$SRC/figures"

mkdir -p "$OUT"

if ! command -v mmdc >/dev/null 2>&1; then
  echo "mermaid-cli not found. Install with: npm install -g @mermaid-js/mermaid-cli" >&2
  exit 1
fi

for f in "$SRC"/*.mermaid; do
  base="$(basename "$f" .mermaid)"
  echo "Rendering $base ..."
  mmdc -i "$f" -o "$OUT/$base.png" -w 2400 -b white
  mmdc -i "$f" -o "$OUT/$base.svg" -b transparent
done

echo "Done. Figures written to $OUT"
