# CLAUDE.md

brickyard builds a Yocto zeus `opkg` feed of extra userspace packages (`.ipk`)
for the Neato LEGO robot. Packages must be **ABI-exact** with the stock
firmware and installable with the robot's built-in `opkg`. `README.md` is for
end users (robot owners); keep build and maintenance details here.

## Target facts

Verified against `firmware/rootfs` (in the parent project, not this repo):

| Property | Value |
|---|---|
| SoC / arch | NXP i.MX8M Nano, aarch64 (tune `aarch64` — *not* cortexa53-crypto) |
| libc | glibc 2.30 |
| Distro | Yocto **zeus**, NXP `rel_imx_5.4.47_2.2.0` pin set (firmware 1.7.0-2933) |
| Key libs | openssl 1.1.1g, python3 3.7.8, systemd 243, gcc runtime 9.2 |
| Package manager | opkg 0.4.1 (already installed, no feeds configured) |
| Kernel | 5.4.47-rt28, custom build |

## Layout

```
conf/local.conf                  bitbake config (CONF_VERSION must stay "1" for zeus)
meta-brickyard/                  our layer (machine + distro + package list)
  conf/machine/imx8mnlego-ddr4.conf
  conf/distro/brickyard.conf
  recipes-feed/packagegroups/packagegroup-brickyard.bb   <- ADD PACKAGES HERE
scripts/fetch-layers.sh          clones poky + meta-openembedded at exact pins
scripts/build-feed.sh            runs the build in an ubuntu:18.04 container
scripts/build-in-container.sh    (used by build-feed.sh; writes bblayers.conf)
scripts/check_versions.py        ABI gate: built libs vs target versions
scripts/make_feed.py             prunes target-owned packages, builds Packages index
opkg-target/opkg-status.txt      snapshot of the robot's installed package list
feed-allow-upgrade.txt           explicit exceptions to the pruning rule
.github/workflows/brickyard.yml  CI build + release publishing
```

Build outputs (`yocto/`, `build/`, `feed/`) are gitignored — never commit them.

## Safety model

The build also compiles the packages' dependencies (glibc, openssl, ...).
Those **must not** end up in the feed — `opkg upgrade` on the robot would
then replace core system libraries and could brick it. `make_feed.py`
therefore drops every package whose name already exists in
`opkg-target/opkg-status.txt`, unless explicitly listed in
`feed-allow-upgrade.txt`. It also drops `-dev`/`-dbg`/`-doc`/`-staticdev`/
`-src`/`-ptest` and `locale-base-*` packages.

Of what's left, only packages reachable from `packagegroup-brickyard` (and
allow-listed ones) via `Depends`/`Recommends` are published; a hard
dependency neither the feed nor the target satisfies fails the script. The
build emits ~3000 sibling packages (perl modules, glibc locales/gconv, ...)
and GitHub caps a release at 1000 assets, so this pruning is load-bearing.

`check_versions.py` does not gate feed contents; it validates the layer pins.
`libc6` mismatch is a hard failure, other critical libs only warn.

## Local build (macOS / Linux)

Prerequisite: Docker. zeus needs a 2018–2020 host toolchain, hence the
ubuntu:18.04 container.

```sh
bash scripts/fetch-layers.sh
bash scripts/build-feed.sh        # first run: 2-5 h; warm cache: minutes
python3 scripts/check_versions.py --deploy build/tmp/deploy/ipk --target opkg-target/opkg-status.txt
python3 scripts/make_feed.py --deploy build/tmp/deploy/ipk --target opkg-target/opkg-status.txt \
    --allow-upgrade feed-allow-upgrade.txt --out feed
ls feed/                          # *.ipk + Packages + Packages.gz
```

## CI build (GitHub Actions)

Workflow `brickyard` (`.github/workflows/brickyard.yml`) runs on manual
dispatch or on `feed-v*` tags. It assumes this directory is the repo root.

Optional R2 build cache (sstate + downloads): set repo secrets
`R2_ACCESS_KEY_ID`, `R2_SECRET_ACCESS_KEY`, `R2_ENDPOINT`
(`https://<accountid>.r2.cloudflarestorage.com`) and `R2_BUCKET`. Without them
every CI build is cold (~2-4 h, within the 6 h job limit).

Releasing: a tag build publishes all feed files as release assets.

```sh
git tag feed-vN && git push origin feed-vN
```

Feed URL: `https://github.com/singular0/brickyard/releases/download/feed-vN`.
Update the tag in `README.md`'s quick start when cutting a release.

## Growing the feed

1. Add package names to `meta-brickyard/recipes-feed/packagegroups/packagegroup-brickyard.bb`.
2. Check the recipe exists in the pinned layers:
   `grep -r "SUMMARY" yocto/meta-openembedded/meta-*/recipes-*/*/<name>*/`
3. Build, run `check_versions.py`, tag a new `feed-vN`.
4. Update the package table in `README.md`.

Kernel modules are out of scope — they must match the robot's exact kernel
build, which we cannot reproduce from these layers.

## Robot-side behaviour worth knowing

zeus `openssh` 8.0p1 is turnkey on the robot: `sshd.socket` listens on port 22
and spawns per-connection `sshd@.service`; `sshdgenkeys.service` generates
missing host keys on the fly; the `sshd` user is created at install time
(target has `useradd`); `/var/run/sshd` is handled via `volatiles.99_sshd`.
Root login is key-only (`PermitRootLogin prohibit-password`, the OpenSSH 8.0
default).

A Neato OTA update rewrites the rootfs, wiping everything installed from the
feed.

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
