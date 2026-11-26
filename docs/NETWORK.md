# Network (hosted)

Linux owns the Wi-Fi hardware; iOS is to reach the network through the host.

## Wi-Fi on the host (works, 2026-11-26)

`wifi-up scan` on the booted image (host/initramfs/wifi-up): the modem boots from the phone's `modem_a` partition (mounted read-only),
`rmtfs` serves copies of the modem storage in RAM, `tqftpserv` serves `wlanmdsp.mbn`, and ath10k_snoc brings up `wlan0`. First run: modem
running, WCN3990 firmware 2.2.5, scan lists the networks around. The drivers probe at boot before `qrtr` is loaded, so the script probes
them again.

The image needs (never committed): Debian arm64 packages `rmtfs tqftpserv libqrtr1 iw wpasupplicant wireless-regdb` and their `libnl`,
`libpcsclite`, `libdbus` libraries unpacked in `$WIFIUSER/root`, linux-firmware's `ath10k/WCN3990/hw1.0/firmware-5.bin` in `$WIFIUSER/fw`,
and `wlanmdsp.mbn`, `bdwlan-bonito.bin` from the phone's vendor image in `$MODEMFW`.

`wifi-join CONF` joins a network (wpa_supplicant configuration, DHCP). Not tested yet: it needs a network's credentials.

Open: the MAC address is random at each boot.

## iOS networking (to do)

A network interface in XNU that exchanges Ethernet frames with a host service, which does DHCP, DNS and NAT in user space (libslirp), so it
works over whatever route Linux has.
