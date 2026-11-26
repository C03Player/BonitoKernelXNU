#!/bin/bash
# Build the sdm670-mainline host kernel for bonito: host/build-mainline.sh [make targets...]   (default: Image.gz dtbs modules)
# Env: SRC (kernel source), OUT (build directory), JOBS. Source: gitlab.com/sdm670-mainline/linux, tag sdm670-v7.3.5_beta2.
set -euo pipefail
HERE=$(cd "$(dirname "$0")" && pwd)
SRC=${SRC:-/usb/work/linux/src}
OUT=${OUT:-/usb/work/linux/out}
J=${JOBS:-4}
M=(make -C "$SRC" O="$OUT" ARCH=arm64)
if [ ! -f "$OUT/.config" ] || [ "$HERE/mainline-host.config" -nt "$OUT/.config" ]; then
	"${M[@]}" defconfig sdm670.config >/dev/null
	(cd "$SRC" && ARCH=arm64 scripts/kconfig/merge_config.sh -m -O "$OUT" "$OUT/.config" "$HERE/mainline-host.config" >/dev/null)
	"${M[@]}" olddefconfig >/dev/null
	# every requested option must have survived dependency resolution
	bad=0
	while IFS='=' read -r k v; do
		case "$k" in CONFIG_*) ;; *) continue ;; esac
		got=$(grep -E "^$k=" "$OUT/.config" | cut -d= -f2- || true)
		[ "$v" = n ] && v=
		[ "$got" = "$v" ] || { echo "config: $k wanted '${v:-n}' got '${got:-n}'"; bad=1; }
	done < "$HERE/mainline-host.config"
	[ $bad = 0 ] || echo "config: some options differ (see above)"
fi
[ "${1:-}" = config ] && exit 0
exec nice "${M[@]}" -j"$J" ${@:-Image.gz dtbs modules}
