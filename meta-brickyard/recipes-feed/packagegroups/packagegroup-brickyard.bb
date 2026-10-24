SUMMARY = "Extra userspace packages for the Neato LEGO robot opkg feed"
DESCRIPTION = "Console tools missing from the stock Neato rootfs. All recipes \
verified present in the pinned zeus layers (poky 5408e48d, meta-openembedded \
2b5dd1eb). Edit this list to grow the feed."

inherit packagegroup

# --- remote access (the first package: stock firmware has NO ssh at all) ---
# zeus openssh 8.0p1 is turnkey for the robot: the sshd package creates the
# sshd user on-device, ships sshdgenkeys.service (host keys auto-generate on
# first connection), and runs socket-activated on port 22.
# Enable on the robot with:  systemctl enable --now sshd.socket
RDEPENDS_${PN} = " \
    openssh-keygen \
    openssh-scp \
    openssh-sftp-server \
    openssh-ssh \
    openssh-sshd \
"

# --- shell & editors ---
RDEPENDS_${PN} += " \
    bash-completion \
    file \
    htop \
    less \
    nano \
    screen \
    tmux \
    tree \
    vim \
"

# --- debugging / tracing ---
RDEPENDS_${PN} += " \
    gdb \
    lsof \
    strace \
"

# --- networking ---
RDEPENDS_${PN} += " \
    curl \
    ethtool \
    iperf3 \
    tcpdump \
    wget \
"

# --- dev / data ---
RDEPENDS_${PN} += " \
    git \
    jq \
    python3-modules \
    rsync \
"

# --- compression (real versions; busybox applets stay untouched) ---
RDEPENDS_${PN} += " \
    gzip \
    bzip2 \
    xz \
    zip \
    unzip \
"
