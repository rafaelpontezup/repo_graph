#!/usr/bin/env bash
set -e
VENDOR_DIR=$(pwd)/vendor
BUILD_DIR=$(pwd)/build
mkdir -p "$VENDOR_DIR" "$BUILD_DIR"

# Clone grammars if not present
if [ ! -d "$VENDOR_DIR/tree-sitter-python" ]; then
  echo "Cloning tree-sitter-python..."
  git clone https://github.com/tree-sitter/tree-sitter-python "$VENDOR_DIR/tree-sitter-python"
else
  echo "tree-sitter-python already exists, pulling..."
  (cd "$VENDOR_DIR/tree-sitter-python" && git pull)
fi

if [ ! -d "$VENDOR_DIR/tree-sitter-java" ]; then
  echo "Cloning tree-sitter-java..."
  git clone https://github.com/tree-sitter/tree-sitter-java "$VENDOR_DIR/tree-sitter-java"
else
  echo "tree-sitter-java already exists, pulling..."
  (cd "$VENDOR_DIR/tree-sitter-java" && git pull)
fi

echo "Building languages bundle..."
python3 - <<'PY'
from tree_sitter import Language
import os
VENDOR = os.path.join(os.getcwd(), "vendor")
BUILD = os.path.join(os.getcwd(), "build", "my-languages.so")
Language.build_library(
    BUILD,
    [
        os.path.join(VENDOR, "tree-sitter-python"),
        os.path.join(VENDOR, "tree-sitter-java"),
    ]
)
print("Built:", BUILD)
PY
echo "Done."
