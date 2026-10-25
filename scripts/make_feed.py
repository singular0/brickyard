#!/usr/bin/env python3
"""Assemble a publishable opkg feed from a Yocto deploy/ipk directory.

Safety model: the robot already has ~710 packages installed (see
target/opkg-status.txt). The feed must only contain packages that are NOT
already on the target (plus an explicit allow-upgrade list), otherwise
`opkg upgrade` on the robot could replace core libraries (glibc, openssl,
systemd, ...) and brick the device.

Of what remains, only packages reachable from the root packagegroup (via
Depends/Recommends) are published. The build also emits thousands of unused
sibling packages (perl modules, glibc locales, ...) that would otherwise
blow past GitHub's 1000-assets-per-release limit.

Output is a single flat directory: *.ipk + Packages + Packages.gz, ready to
upload to a GitHub release or any static HTTP host.
"""
import argparse
import gzip
import io
import os
import re
import shutil
import sys
import tarfile

# Package suffixes that never belong on the robot
SKIP_SUFFIXES = ("-dbg", "-dev", "-doc", "-staticdev", "-src", "-ptest")
SKIP_PREFIXES = ("locale-base-",)


def iter_ar_members(buf):
    """Yield (name, data) for each member of an ar archive (ipk/deb)."""
    if buf[:8] != b"!<arch>\n":
        raise ValueError("not an ar archive")
    off = 8
    while off + 60 <= len(buf):
        hdr = buf[off:off + 60]
        name = hdr[0:16].decode().strip().rstrip("/")
        size = int(hdr[48:58].decode().strip())
        data = buf[off + 60:off + 60 + size]
        yield name, data
        off += 60 + size + (size % 2)  # members are 2-byte aligned


def read_control(ipk_path):
    """Extract the control stanza (as an ordered dict-ish list) from an ipk."""
    with open(ipk_path, "rb") as f:
        buf = f.read()
    for name, data in iter_ar_members(buf):
        if name == "control.tar.gz":
            with tarfile.open(fileobj=io.BytesIO(data), mode="r:gz") as tf:
                for m in tf.getmembers():
                    if m.name.lstrip("./") == "control":
                        return parse_stanza(tf.extractfile(m).read().decode())
    raise ValueError(f"{ipk_path}: no control member")


def parse_stanza(text):
    """Parse a debian-style control stanza into a list of (field, value)."""
    fields = []
    for line in text.splitlines():
        if not line:
            continue
        if line[0] in " \t" and fields:
            fields[-1][1] += "\n" + line
        elif ":" in line:
            k, v = line.split(":", 1)
            fields.append([k.strip(), v.strip()])
    return fields


def stanza_get(fields, key, default=""):
    for k, v in fields:
        if k == key:
            return v
    return default


def iter_deploy_ipks(deploy_dir):
    """Yield (path, control_fields) for every ipk in the deploy tree."""
    for root, _dirs, files in os.walk(deploy_dir):
        for fn in sorted(files):
            if fn.endswith(".ipk"):
                path = os.path.join(root, fn)
                try:
                    yield path, read_control(path)
                except Exception as e:
                    print(f"warning: skipping unreadable {fn}: {e}", file=sys.stderr)


def load_target_names(status_path):
    names = set()
    with open(status_path) as f:
        for line in f:
            if line.startswith("Package: "):
                names.add(line.split(":", 1)[1].strip())
    return names


def load_target_provides(status_path):
    """Names the target satisfies: its packages plus their Provides."""
    names = set()
    with open(status_path) as f:
        for line in f:
            if line.startswith(("Package: ", "Provides: ")):
                for alts in parse_deps(line.split(":", 1)[1]):
                    names.update(alts)
    return names


def parse_deps(value):
    """Parse 'a (>= 1), b | c' into [['a'], ['b', 'c']], dropping versions."""
    deps = []
    for item in value.split(","):
        alts = [re.sub(r"\(.*?\)", "", a).strip() for a in item.split("|")]
        alts = [a for a in alts if a]
        if alts:
            deps.append(alts)
    return deps


def reachable(roots, candidates, target_provides, allow):
    """Return candidate names reachable from roots via Depends/Recommends.

    Dependencies the target already satisfies are not followed (unless
    allow-listed). Returns (names, unresolved) where unresolved lists
    hard Depends that neither the feed nor the target can satisfy.
    """
    provider = {}
    for name, entries in candidates.items():
        provider.setdefault(name, name)
        for _path, fields in entries:
            for alts in parse_deps(stanza_get(fields, "Provides")):
                for a in alts:
                    provider.setdefault(a, name)

    seen, unresolved = set(), []
    stack = [r for r in roots if r in candidates]
    while stack:
        name = stack.pop()
        if name in seen:
            continue
        seen.add(name)
        for _path, fields in candidates[name]:
            for field in ("Depends", "Recommends"):
                for alts in parse_deps(stanza_get(fields, field)):
                    if any(a in target_provides and a not in allow for a in alts):
                        continue
                    hit = next((provider[a] for a in alts if a in provider), None)
                    if hit:
                        stack.append(hit)
                    elif field == "Depends":
                        unresolved.append(f"{name}: {' | '.join(alts)}")
    return seen, unresolved


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--deploy", required=True, help="build/tmp/deploy/ipk")
    ap.add_argument("--target", required=True, help="target opkg status file")
    ap.add_argument("--allow-upgrade", default=None,
                    help="file with package names allowed to shadow target packages")
    ap.add_argument("--root", default="packagegroup-brickyard",
                    help="packagegroup whose dependency closure is published")
    ap.add_argument("--out", required=True, help="output feed directory")
    args = ap.parse_args()

    target_names = load_target_names(args.target)
    target_provides = load_target_provides(args.target)
    allow = set()
    if args.allow_upgrade and os.path.exists(args.allow_upgrade):
        with open(args.allow_upgrade) as f:
            allow = {l.strip() for l in f if l.strip() and not l.startswith("#")}

    candidates = {}
    skipped_target = skipped_aux = 0

    for path, fields in iter_deploy_ipks(args.deploy):
        pkg = stanza_get(fields, "Package")
        if not pkg:
            continue
        if pkg in target_names and pkg not in allow:
            skipped_target += 1
            continue
        if pkg.endswith(SKIP_SUFFIXES) or pkg.startswith(SKIP_PREFIXES):
            skipped_aux += 1
            continue
        candidates.setdefault(pkg, []).append((path, fields))

    if args.root not in candidates:
        sys.exit(f"error: root package {args.root} not found in {args.deploy}")
    wanted, unresolved = reachable([args.root, *allow], candidates,
                                   target_provides, allow)
    if unresolved:
        print("error: dependencies not satisfiable by feed or target:", file=sys.stderr)
        for u in unresolved:
            print(f"  {u}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(args.out, exist_ok=True)
    stanzas = []
    kept = 0
    total_bytes = 0
    skipped_unused = sum(len(v) for k, v in candidates.items() if k not in wanted)

    for path, fields in (e for k in sorted(wanted) for e in candidates[k]):
        fn = os.path.basename(path)
        shutil.copy2(path, os.path.join(args.out, fn))
        total_bytes += os.path.getsize(path)

        # rewrite Filename to the flat feed layout
        out_fields = [[k, v] for k, v in fields if k != "Filename"]
        out_fields.append(["Filename", fn])
        stanzas.append(out_fields)
        kept += 1

    stanzas.sort(key=lambda f: stanza_get(f, "Package").lower())
    # stanzas must be separated by a blank line, or opkg reads one package
    index = "\n\n".join(
        "\n".join(f"{k}: {v}" for k, v in fields) for fields in stanzas
    ) + "\n"
    with open(os.path.join(args.out, "Packages"), "w") as f:
        f.write(index)
    with gzip.open(os.path.join(args.out, "Packages.gz"), "wb") as f:
        f.write(index.encode())

    print(f"feed assembled in {args.out}")
    print(f"  kept:              {kept} packages ({total_bytes / 1e6:.1f} MB)")
    print(f"  skipped (on target): {skipped_target}")
    print(f"  skipped (aux):     {skipped_aux}")
    print(f"  skipped (unused):  {skipped_unused}")


if __name__ == "__main__":
    main()
