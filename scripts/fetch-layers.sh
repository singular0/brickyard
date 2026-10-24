#!/usr/bin/env bash
# Fetch the Yocto layers at the exact pins used by NXP rel_imx_5.4.47_2.2.0,
# which is what the Neato LEGO firmware (1.7.0-2933) was built from.
# Verified against the target rootfs: glibc 2.30, openssl 1.1.1g, python3 3.7.8,
# gcc runtime 9.2, systemd 243.
set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
YOCTO_DIR="${YOCTO_DIR:-$HERE/yocto}"

POKY_URL="https://github.com/yoctoproject/poky.git"
POKY_REV="5408e48d374fc741fa46b57ddfd8a537843bda6f"

OE_URL="https://github.com/openembedded/meta-openembedded.git"
OE_REV="2b5dd1eb81cd08bc065bc76125f2856e9383e98b"

fetch() {
    local url="$1" rev="$2" dir="$3"
    if [ -d "$dir/.git" ] && [ "$(git -C "$dir" rev-parse HEAD)" = "$rev" ]; then
        echo "== $dir already at $rev"
        return
    fi
    echo "== fetching $url @ $rev"
    mkdir -p "$dir"
    git -C "$dir" init -q
    git -C "$dir" remote remove origin 2>/dev/null || true
    git -C "$dir" remote add origin "$url"
    git -C "$dir" fetch -q --depth 1 origin "$rev"
    git -C "$dir" checkout -q FETCH_HEAD
}

fetch "$POKY_URL" "$POKY_REV" "$YOCTO_DIR/poky"
fetch "$OE_URL"   "$OE_REV"   "$YOCTO_DIR/meta-openembedded"

echo "== layers ready in $YOCTO_DIR"
