#!/usr/bin/env python3
"""ABI sanity check: compare versions of critical packages in the Yocto
deploy dir against the versions actually installed on the robot.

This does NOT gate what goes into the feed (make_feed.py prunes target
packages anyway) — it validates that you pinned the right Yocto layers.
If libc6 comes out as anything but 2.30.x, your packages may not run on
the robot. Exit code 1 on hard mismatch.
"""
import argparse
import sys

from make_feed import iter_deploy_ipks, stanza_get

# name -> severity: "hard" fails the build, "warn" just prints
CRITICAL = {
    "libc6": "hard",
    "libgcc1": "warn",
    "libstdc++6": "warn",
    "libcrypto1.1": "warn",
    "libssl1.1": "warn",
    "zlib": "warn",
    "systemd": "warn",
    "bash": "warn",
    "python3-core": "warn",
    "libarchive": "warn",
}


def load_target_versions(status_path):
    vers = {}
    name = None
    with open(status_path) as f:
        for line in f:
            line = line.rstrip("\n")
            if line.startswith("Package: "):
                name = line.split(":", 1)[1].strip()
            elif line.startswith("Version: ") and name:
                vers[name] = line.split(":", 1)[1].strip()
                name = None
    return vers


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", required=True)
    ap.add_argument("--target", required=True)
    args = ap.parse_args()

    target = load_target_versions(args.target)

    built = {}
    for _path, fields in iter_deploy_ipks(args.deploy):
        pkg = stanza_get(fields, "Package")
        ver = stanza_get(fields, "Version")
        if pkg in CRITICAL and pkg not in built:
            built[pkg] = ver

    print(f"{'package':<16} {'target':<22} {'built':<22} verdict")
    failures = 0
    for pkg, severity in CRITICAL.items():
        t = target.get(pkg, "(absent)")
        b = built.get(pkg, "(not built)")
        if t == "(absent)" or b == "(not built)":
            verdict = "skip"
        else:
            # compare the upstream part, ignoring the -rN revision
            t_base, b_base = t.split("-")[0], b.split("-")[0]
            if t_base == b_base:
                verdict = "OK"
            elif severity == "hard":
                verdict = "FAIL"
                failures += 1
            else:
                verdict = "WARN"
        print(f"{pkg:<16} {t:<22} {b:<22} {verdict}")

    if failures:
        print("\nHARD MISMATCH: built glibc does not match the target. "
              "Fix the layer pins in scripts/fetch-layers.sh.", file=sys.stderr)
        sys.exit(1)
    print("\nABI check passed.")


if __name__ == "__main__":
    main()
