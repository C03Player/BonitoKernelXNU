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

## iOS networking (link works, 2026-11-27)

en0 in XNU (`bsd/dev/linux64_net_link.c`, boot-arg `linux64net=1`, set by `xnu-run`; `XNU_NET=0` leaves it out) exchanges frames with the
Linux device `xnu0` that `fki.ko` creates. `xnu-net` on the host gives `xnu0` 192.168.77.1, runs dnsmasq (DHCP, DNS forwarding to
`/etc/resolv.conf`) and masquerades everything else with nftables.

configd configures en0 only when it finds it as an Ethernet interface in the registry (`RedwoodEthernet`) and when an `IONetworkStack`
service exists (`MiniIONetworkStack`, otherwise it waits). Verified with build 45913646691: DHCP lease 192.168.77.10, default route via
192.168.77.1, the host pings the phone's iOS.

    wifi-up; XNU_CPUS=4 xnu-run; xnu-net; wifi-join /tmp/wifi.conf

Not tested: traffic to the internet (no network joined yet).

Debugging: `XNU_BOOTARGS="net_names=1 net_trace=60 sweetiolog=configd"`; with `hfsplus` the host can mount the live iOS volume read-only.
