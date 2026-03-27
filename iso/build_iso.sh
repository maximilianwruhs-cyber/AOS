#!/bin/bash
# ============================================================
# AOS Custom ISO Builder
# Build a zero-touch Ubuntu 24.04 Desktop ISO with all
# dependencies pre-baked (offline deployment ready).
#
# Prerequisites: xorriso, squashfs-tools, rsync, curl
#   sudo apt install xorriso squashfs-tools rsync curl
#
# Usage: sudo ./build_iso.sh [/path/to/ubuntu-24.04-desktop.iso]
# ============================================================
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
AOS_REPO="https://github.com/maximilianwruhs-cyber/AOS.git"

ISO_URL="https://releases.ubuntu.com/24.04/ubuntu-24.04.1-desktop-amd64.iso"
ISO_NAME="${1:-ubuntu-24.04-desktop.iso}"
CUSTOM_ISO="aos-installer-24.04.iso"
WORK_DIR="$SCRIPT_DIR/iso_work"

# ─── Preflight checks ────────────────────────────────────────
if [ "$EUID" -ne 0 ]; then
    echo "❌ Must run as root (sudo ./build_iso.sh)"
    exit 1
fi

for cmd in xorriso unsquashfs mksquashfs rsync curl chroot; do
    if ! command -v "$cmd" &> /dev/null; then
        echo "❌ Missing: $cmd. Install with: apt install xorriso squashfs-tools rsync curl"
        exit 1
    fi
done

mkdir -p "$WORK_DIR"/{mnt,iso,chroot}

# ─── 1. Download ISO (if not provided) ───────────────────────
if [ ! -f "$ISO_NAME" ]; then
    echo "=> 1. Downloading Ubuntu 24.04 Desktop ISO..."
    curl -L -o "$ISO_NAME" "$ISO_URL"
else
    echo "=> 1. Using existing ISO: $ISO_NAME"
fi

# ─── 2. Extract ISO contents ─────────────────────────────────
echo "=> 2. Extracting ISO contents..."
mount -o loop "$ISO_NAME" "$WORK_DIR/mnt" 2>/dev/null || true
rsync -a "$WORK_DIR/mnt/" "$WORK_DIR/iso/"
umount "$WORK_DIR/mnt" 2>/dev/null || true

# ─── 3. Extract SquashFS root filesystem ─────────────────────
echo "=> 3. Extracting SquashFS root filesystem..."
SQUASH_FILE=$(ls "$WORK_DIR"/iso/casper/*.squashfs 2>/dev/null | head -n 1)
if [ -z "$SQUASH_FILE" ]; then
    echo "❌ No .squashfs found in casper/. Is this a valid Ubuntu Desktop ISO?"
    exit 1
fi
unsquashfs -f -d "$WORK_DIR/chroot" "$SQUASH_FILE"

# ─── 4. Setup chroot mounts ─────────────────────────────────
echo "=> 4. Setting up chroot environment..."
mount --bind /dev "$WORK_DIR/chroot/dev"
mount --bind /run "$WORK_DIR/chroot/run"
mount -t proc /proc "$WORK_DIR/chroot/proc"
mount -t sysfs /sys "$WORK_DIR/chroot/sys"
cp /etc/resolv.conf "$WORK_DIR/chroot/etc/resolv.conf"

# ─── 5. Install software inside chroot ───────────────────────
echo "=> 5. Installing AOS dependencies inside chroot..."
# IMPORTANT: Never run 'apt upgrade' — it can break the installer snap!
cat << 'CHROOT_SCRIPT' | chroot "$WORK_DIR/chroot" /bin/bash
export DEBIAN_FRONTEND=noninteractive
apt-get update

# Core packages
# NOTE: libfuse2t64 (not libfuse2!) — Ubuntu 24.04 Time64 transition
apt-get install -y \
    openssh-server curl git python3.12-venv libfuse2t64 ansible \
    xvfb  # For headless LM Studio

# Node.js 22 (for Gemini CLI, OpenClaw)
curl -fsSL https://deb.nodesource.com/setup_22.x | bash -
apt-get install -y nodejs
npm install -g @google/gemini-cli openclaw 2>/dev/null || true

# Ollama Binary
echo "   Installing Ollama..."
curl -L https://ollama.com/download/ollama-linux-amd64 -o /usr/local/bin/ollama
chmod +x /usr/local/bin/ollama

# LM Studio AppImage
echo "   Installing LM Studio..."
mkdir -p /opt/lm-studio
curl -L "https://lmstudio.ai/download/latest/linux/x64" -o /opt/lm-studio/LM_Studio.AppImage
chmod +x /opt/lm-studio/LM_Studio.AppImage

# AOS Repository + Python venv
echo "   Setting up AOS..."
mkdir -p /opt/aos
git clone https://github.com/maximilianwruhs-cyber/AOS.git /opt/aos/repo || true
python3 -m venv /opt/aos/.venv
/opt/aos/.venv/bin/pip install --no-cache-dir fastapi uvicorn httpx psutil python-dotenv

# Pre-pull Ollama model (offline ready)
echo "   Pre-pulling qwen2.5-coder:1.5b model..."
export OLLAMA_MODELS=/usr/share/ollama/.ollama/models
mkdir -p "$OLLAMA_MODELS"
nohup ollama serve > /dev/null 2>&1 &
sleep 5
ollama pull qwen2.5-coder:1.5b || echo "   ⚠️ Model pull failed (will need online pull later)"
pkill ollama 2>/dev/null || true

# Cleanup (shrink ISO size)
apt-get clean
rm -rf /var/lib/apt/lists/* /tmp/* /var/tmp/*
CHROOT_SCRIPT

# ─── 6. Teardown chroot ─────────────────────────────────────
echo "=> 6. Cleaning up chroot mounts..."
umount "$WORK_DIR/chroot/sys" 2>/dev/null || true
umount "$WORK_DIR/chroot/proc" 2>/dev/null || true
umount "$WORK_DIR/chroot/run" 2>/dev/null || true
umount "$WORK_DIR/chroot/dev" 2>/dev/null || true
rm -f "$WORK_DIR/chroot/etc/resolv.conf"

# ─── 7. Repack SquashFS (zstd compression) ───────────────────
echo "=> 7. Repacking SquashFS (this takes several minutes)..."
rm "$SQUASH_FILE"
mksquashfs "$WORK_DIR/chroot" "$SQUASH_FILE" -comp zstd -b 1M -noappend
printf $(du -sx --block-size=1 "$WORK_DIR/chroot" | cut -f1) > "${SQUASH_FILE%.squashfs}.size"

# ─── 8. Inject Autoinstall config ────────────────────────────
echo "=> 8. Injecting autoinstall configuration..."
mkdir -p "$WORK_DIR/iso/nocloud"
cp "$SCRIPT_DIR/autoinstall.yaml" "$WORK_DIR/iso/nocloud/user-data"
touch "$WORK_DIR/iso/nocloud/meta-data"

# Modify GRUB: add autoinstall params, reduce timeout
sed -i 's/quiet splash/quiet splash autoinstall ds=nocloud\\;s=\/cdrom\/nocloud\/ ---/g' \
    "$WORK_DIR/iso/boot/grub/grub.cfg"
sed -i 's/quiet splash/quiet splash autoinstall ds=nocloud\\;s=\/cdrom\/nocloud\/ ---/g' \
    "$WORK_DIR/iso/boot/grub/loopback.cfg" 2>/dev/null || true
sed -i 's/set timeout=30/set timeout=3/g' "$WORK_DIR/iso/boot/grub/grub.cfg"

# Update checksums
cd "$WORK_DIR/iso" && find . -type f -print0 | xargs -0 md5sum | grep -v "\./md5sum.txt" > md5sum.txt && cd "$OLDPWD"

# ─── 9. Build hybrid ISO (UEFI + Legacy BIOS) ────────────────
echo "=> 9. Building hybrid ISO (UEFI + Legacy BIOS)..."
# Extract MBR boot sector from original ISO for legacy boot compatibility
dd if="$ISO_NAME" bs=1 count=432 of="$WORK_DIR/isohdpfx.bin" 2>/dev/null

xorriso -as mkisofs -r -V "AOS_INSTALLER" \
    -J -l -b boot/grub/i386-pc/eltorito.img -c boot.catalog -no-emul-boot \
    -boot-load-size 4 -boot-info-table \
    -eltorito-alt-boot -e EFI/boot/bootx64.efi -no-emul-boot \
    -isohybrid-gpt-basdat -isohybrid-apm-hfsplus \
    -isohybrid-mbr "$WORK_DIR/isohdpfx.bin" \
    -o "$CUSTOM_ISO" "$WORK_DIR/iso"

# ─── 10. Summary ─────────────────────────────────────────────
ISO_SIZE=$(du -sh "$CUSTOM_ISO" | cut -f1)
echo ""
echo "============================================================"
echo "  ✅ AOS Custom ISO built successfully!"
echo "  📁 Image: $CUSTOM_ISO ($ISO_SIZE)"
echo ""
echo "  Write to USB:"
echo "    sudo dd if=$CUSTOM_ISO of=/dev/sdX bs=4M status=progress"
echo ""
echo "  Or use BalenaEtcher / Rufus (DD mode)"
echo "============================================================"
