#!/usr/bin/env bash
# Build the feed inside an era-correct Ubuntu 18.04 container (zeus needs a
# 2018-2020 toolchain on the host). Works the same locally (macOS Docker
# Desktop) and in GitHub Actions.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
IMAGE="${POKY_HOST_IMAGE:-ubuntu:18.04}"
NPROC="$(nproc 2>/dev/null || sysctl -n hw.ncpu)"

mkdir -p "$HERE/yocto/downloads" "$HERE/yocto/sstate-cache"

docker run --rm \
    -v "$HERE":/work \
    -w /work \
    -e BB_NUMBER_THREADS="${BB_NUMBER_THREADS:-$NPROC}" \
    "$IMAGE" bash /work/scripts/build-in-container.sh
