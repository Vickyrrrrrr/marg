#!/usr/bin/env bash
set -euo pipefail
ROOT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
export GHIDRA_INSTALL_DIR="$ROOT_DIR/analysis/ghidra_12.1.4_PUBLIC"
export JAVA_HOME="$ROOT_DIR/analysis/jdk/usr/lib/jvm/java-21-openjdk-amd64"
export PATH="$JAVA_HOME/bin:$ROOT_DIR/analysis/runtime/node_modules/node/bin:$PATH"
exec "$ROOT_DIR/analysis/rea/node_modules/.bin/rea" "$@"
