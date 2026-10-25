# brickyard — extra packages for the Neato LEGO robot

An `opkg` package feed that adds the tools the stock Neato firmware is missing:
SSH, editors, debuggers, network tools and more. Packages are built against
the exact same libraries as the robot's firmware and install with the `opkg`
that's already on it — no reflashing, no custom image.

## Compatibility

Built for the Neato LEGO robot (NXP i.MX8M Nano, aarch64) running the stock
firmware based on Yocto zeus (glibc 2.30). It won't work on other robots or
other firmware lines.

## Quick start

On the robot, as root, add the feed and install what you need:

```sh
cat >> /etc/opkg/opkg.conf <<'EOF'
src/gz brickyard https://github.com/singular0/brickyard/releases/download/feed-v1
EOF
opkg update
opkg install htop tmux vim
```

Replace `feed-v1` with the newest tag listed on the
[Releases](https://github.com/singular0/brickyard/releases) page.

## Enabling SSH

The stock firmware has no SSH client or server. To log in remotely:

```sh
opkg install openssh-sshd openssh-sftp-server
mkdir -p /home/root/.ssh
echo 'ssh-ed25519 AAAA... you@laptop' >> /home/root/.ssh/authorized_keys
systemctl enable --now sshd.socket
```

Host keys are generated automatically on the first connection. Root login is
**key-only** by default; to allow password login, edit `/etc/ssh/sshd_config`.

## Available packages

| Category | Packages |
|---|---|
| Remote access | `openssh-sshd`, `openssh-ssh`, `openssh-scp`, `openssh-sftp-server`, `openssh-keygen` |
| Shell & editors | `bash-completion`, `file`, `htop`, `less`, `nano`, `screen`, `tmux`, `tree`, `vim` |
| Debugging | `gdb`, `lsof`, `strace` |
| Networking | `curl`, `ethtool`, `iperf3`, `tcpdump`, `wget` |
| Dev & data | `git`, `jq`, `python3-modules` (full Python 3.7 standard library), `rsync` |
| Compression | `gzip`, `bzip2`, `xz`, `zip`, `unzip` |

Dependencies pulled in by these are in the feed too. Run `opkg list` after
`opkg update` to see everything.

## Good to know

- **The feed never touches system packages.** Anything that already ships
  with the stock firmware (glibc, openssl, systemd, …) is left out, so
  `opkg install` and `opkg upgrade` can't replace core libraries.
- **No kernel modules.** The robot runs a custom kernel build that can't be
  reproduced, so the feed contains userspace software only.

## Requesting a package

Open an issue with the package name. Anything with a recipe in Yocto zeus
(poky or meta-openembedded) can usually be added.
