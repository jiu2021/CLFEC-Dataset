#!/usr/bin/env bash
# End-to-end: normalize raw model output, then score against CLFEC gold.
#
# Usage:
#   bash run_eval.sh <raw_model_output.json> [output_dir]
#
# <raw_model_output.json> must follow the input format of normalize.py
# (see normalize.py docstring or eval/README.md).
#
# If your model already emits prediction files in CLFEC.json schema (with
# `cors`), skip normalization and call eval.py directly.

set -euo pipefail

PY="${PYTHON:-python3}"

RAW="${1:?raw model output required}"
OUT_DIR="${2:-./results}"
HERE="$(cd "$(dirname "$0")"; pwd)"
GOLD="$(cd "$HERE/.."; pwd)/data/CLFEC.json"

mkdir -p "$OUT_DIR"

base="$(basename "$RAW" .json)"
NORMALIZED="$OUT_DIR/${base}_normalized.json"

echo "[1/2] Normalizing raw model output → $NORMALIZED"
"$PY" "$HERE/normalize.py" \
    --input "$RAW" \
    --output "$NORMALIZED"

echo "[2/2] Scoring against $GOLD"
"$PY" "$HERE/eval.py" \
    --gold "$GOLD" \
    --pred "$NORMALIZED" \
    --mode both \
    --overlap-threshold 0.5 \
    --output-dir "$OUT_DIR"
