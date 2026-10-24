#!/usr/bin/env bash
# Runs INSIDE the ubuntu:18.04 build container. Do not run on the host.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
YOCTO_DIR="$HERE/yocto"
BUILD_DIR="$HERE/build"

# --- 1. Host dependencies -------------------------------------------------
# Ubuntu 18.04 is EOL; its repos moved to old-releases.ubuntu.com.
if ! apt-get update -qq 2>/dev/null; then
    echo "== apt repos unreachable, switching to old-releases.ubuntu.com"
    sed -i -e 's|archive.ubuntu.com|old-releases.ubuntu.com|g' \
           -e 's|security.ubuntu.com|old-releases.ubuntu.com|g' \
           /etc/apt/sources.list
    apt-get update -qq
fi

DEBIAN_FRONTEND=noninteractive apt-get install -y -qq --no-install-recommends \
    build-essential chrpath cpio debianutils diffstat file gawk gcc-multilib git \
    iputils-ping libegl1-mesa libsdl1.2-dev locales python python3 python3-git \
    python3-jinja2 python3-pexpect python3-pip socat texinfo unzip wget xterm \
    xz-utils

locale-gen en_US.UTF-8
export LANG=en_US.UTF-8

# --- 2. Layers ------------------------------------------------------------
if [ ! -d "$YOCTO_DIR/poky/meta" ]; then
    bash "$HERE/scripts/fetch-layers.sh"
fi

# --- 3. Build as non-root (bitbake refuses to run as root) ----------------
useradd -m builder 2>/dev/null || true
mkdir -p "$BUILD_DIR" "$YOCTO_DIR/downloads" "$YOCTO_DIR/sstate-cache"
chown -R builder:builder "$BUILD_DIR" "$YOCTO_DIR/downloads" "$YOCTO_DIR/sstate-cache"

su builder -s /bin/bash <<EOF
set -euo pipefail
cd "$HERE"
# oe-init-build-env reads unset variables (BBSERVER, ...), so relax -u for it.
set +u
source "$YOCTO_DIR/poky/oe-init-build-env" "$BUILD_DIR"
set -u

cp "$HERE/conf/local.conf" conf/local.conf
cat > conf/bblayers.conf <<'BBEOF'
LCONF_VERSION = "7"
BBPATH = "\${TOPDIR}"
BBFILES ?= ""
BBLAYERS ?= " \\
  $HERE/yocto/poky/meta \\
  $HERE/yocto/poky/meta-poky \\
  $HERE/yocto/meta-openembedded/meta-oe \\
  $HERE/yocto/meta-openembedded/meta-python \\
  $HERE/yocto/meta-openembedded/meta-networking \\
  $HERE/yocto/meta-openembedded/meta-filesystems \\
  $HERE/meta-brickyard \\
"
BBEOF

echo "== building packagegroup-brickyard (threads: \${BB_NUMBER_THREADS:-4})"
bitbake packagegroup-brickyard
EOF

echo "== build finished; ipks are in $BUILD_DIR/tmp/deploy/ipk"
