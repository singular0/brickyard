# brickyard — Yocto zeus package feed for the Neato LEGO robot

Builds extra userspace packages (`.ipk`) that are **ABI-exact** with the stock
Neato firmware and installable with the robot's built-in `opkg`.

Target facts (verified against `firmware/rootfs`):

| Property | Value |
|---|---|
| SoC / arch | NXP i.MX8M Nano, aarch64 (tune `aarch64` — *not* cortexa53-crypto) |
| libc | glibc 2.30 |
| Distro | Yocto **zeus**, NXP `rel_imx_5.4.47_2.2.0` pin set |
| Key libs | openssl 1.1.1g, python3 3.7.8, systemd 243, gcc runtime 9.2 |
| Package manager | opkg 0.4.1 (already installed, no feeds configured) |

## Layout

```
conf/local.conf                 bitbake config
meta-brickyard/                our layer (machine + distro + package list)
  conf/machine/imx8mnlego-ddr4.conf
  conf/distro/brickyard.conf
  recipes-feed/packagegroups/packagegroup-brickyard.bb   <- ADD PACKAGES HERE
scripts/fetch-layers.sh         clones poky + meta-openembedded at exact pins
scripts/build-feed.sh           runs the build in an ubuntu:18.04 container
scripts/build-in-container.sh   (used by build-feed.sh)
scripts/check_versions.py       ABI gate: built libs vs target versions
scripts/make_feed.py            prunes target-owned packages, builds Packages index
opkg-target/opkg-status.txt          snapshot of the robot's installed package list
feed-allow-upgrade.txt          explicit exceptions to the pruning rule
.github/workflows/build-feed.yml
```

## Safety model

The build also compiles the packages' dependencies (glibc, openssl, ...).
Those **must not** end up in the feed — `opkg upgrade` on the robot would
then replace core system libraries and could brick it. `make_feed.py`
therefore drops every package whose name already exists in
`opkg-target/opkg-status.txt`, unless explicitly listed in
`feed-allow-upgrade.txt`. It also drops `-dev`/`-dbg`/`-doc`/`-src` packages.

## Local build (macOS / Linux)

Prerequisite: Docker Desktop (free for personal use).

```sh
cd packages   # = this repo (brickyard)
bash scripts/build-feed.sh        # first run: 2-5 h; warm cache: minutes
python3 scripts/check_versions.py --deploy build/tmp/deploy/ipk --target opkg-target/opkg-status.txt
python3 scripts/make_feed.py --deploy build/tmp/deploy/ipk --target opkg-target/opkg-status.txt \
    --allow-upgrade feed-allow-upgrade.txt --out feed
ls feed/                          # *.ipk + Packages + Packages.gz
```

## CI build (free, GitHub Actions)

1. Push this directory as a **public** GitHub repo (unlimited free minutes).
2. Optional but recommended — R2 build cache (free tier, 10 GB):
   create a bucket and set repo secrets `R2_ACCESS_KEY_ID`,
   `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT` (`https://<accountid>.r2.cloudflarestorage.com`),
   `R2_BUCKET`. Without these, every CI build is cold (~2-4 h, still within
   the 6 h job limit).
3. Actions → *build-feed* → Run workflow, or tag a release:

```sh
git tag feed-v1 && git push origin feed-v1
```

A tag build publishes all feed files as release assets. The feed URL is then:

```
https://github.com/<USER>/<REPO>/releases/download/feed-v1/
```

## Installing on the robot

```sh
cat >> /etc/opkg/opkg.conf <<'EOF'
src/gz brickyard https://github.com/<USER>/<REPO>/releases/download/feed-v1
EOF
opkg update
opkg install htop tmux openssh
```

### The first package: native sshd

Stock firmware has **no SSH client or server at all**. Install from the feed:

```sh
opkg install openssh-sshd openssh-sftp-server
systemctl enable --now sshd.socket
```

That's it — no key generation step needed. The zeus `openssh` package is
turnkey on the robot:

- `sshd.socket` listens on port 22 and spawns a per-connection `sshd@.service`
- `sshdgenkeys.service` runs first and generates missing host keys on the fly
- the `sshd` user is created automatically at install time (target has
  `useradd`), and `/var/run/sshd` is handled via `volatiles.99_sshd`

Root login is **key-only** (`PermitRootLogin prohibit-password` is the
OpenSSH 8.0 default) — drop your pubkey into `/home/root/.ssh/authorized_keys`
first. If you want password login, edit `/etc/ssh/sshd_config` on the robot.

Note: a Neato OTA update rewrites the rootfs — your sshd, keys and
`authorized_keys` go with it. Re-run the three commands above after an update.

## Growing the feed

1. Add package names to `meta-brickyard/recipes-feed/packagegroups/packagegroup-brickyard.bb`.
2. Check the recipe exists in the pinned layers:
   `grep -r "SUMMARY" yocto/meta-openembedded/meta-*/recipes-*/*/<name>*/`
3. Build, run `check_versions.py`, tag a new `feed-vN`.

Kernel modules are out of scope — they must match the robot's exact kernel
build (5.4.47-rt28 custom), which we cannot reproduce from these layers.

## Troubleshooting

- **"nothing provides X"** — the recipe doesn't exist in the pinned layers;
  find which layer carries it and add that sublayer to `bblayers.conf` in
  `scripts/build-in-container.sh`.
- **Disk pressure on GH runner** — `rm_work` is already enabled; if a build
  still fills up, trim the package list or split into two jobs.
- **ABI check FAIL on libc6** — wrong poky pin; adjust `POKY_REV` in
  `scripts/fetch-layers.sh` (target needs glibc 2.30).
- **After a Neato OTA update** — refresh `opkg-target/opkg-status.txt` from the
  new rootfs and re-tag; package versions may have moved.
