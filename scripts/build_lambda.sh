#!/usr/bin/env bash
# Build Lambda artifacts without Docker: pure-Python source zip + ARM64
# manylinux wheel layer. Outputs under build/ (git-ignored).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd -W 2>/dev/null || pwd)"
BUILD="$ROOT/build"
SRC_STAGE="$BUILD/lambda-src"
LAYER="$BUILD/layer"
PY="${PYTHON:-$ROOT/.venv/Scripts/python.exe}"

rm -rf "$BUILD"
mkdir -p "$SRC_STAGE/gatehouse/channels" "$SRC_STAGE/packs/in" "$LAYER/python"

# 1) source tree, re-rooted for Lambda import
cp -r "$ROOT/src/gatehouse/." "$SRC_STAGE/gatehouse/"
find "$SRC_STAGE" -type d -name "__pycache__" -prune -exec rm -rf {} +
mkdir -p "$SRC_STAGE/packs/in"
cp "$ROOT"/packs/in/*.yaml "$SRC_STAGE/packs/in/"

"$PY" -c "import shutil; shutil.make_archive(r'$BUILD/lambda-src', 'zip', r'$SRC_STAGE')"

# 2) dependencies layer: linux/aarch64 wheels via uv (venv has no pip)
uv pip install \
  --python "$PY" \
  --target "$LAYER/python" \
  --python-platform aarch64-unknown-linux-gnu \
  --python-version 3.12 \
  --only-binary :all: \
  "strands-agents>=0.2" "pydantic>=2.7" "pydantic-settings>=2.2" \
  "PyYAML>=6.0" "fastapi>=0.111" "mangum>=0.18" "boto3>=1.34"

"$PY" -c "import shutil; shutil.make_archive(r'$BUILD/lambda-layer', 'zip', r'$LAYER')"

echo "artifacts:"
ls -la "$BUILD"/*.zip
