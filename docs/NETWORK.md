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

The USB link to the PC is 172.31.254.0/30 (phone .2). It was 192.168.7.0/24 until a real network with those addresses was joined
(2026-11-27): the route to its router and name server then pointed down the cable, so no name resolved. The clock must be right as well:
the init script sets it after loading the modules, whose PMIC clock driver otherwise leaves it in 1970.

## iOS networking (link works, 2026-11-27)

en0 in XNU (`bsd/dev/linux64_net_link.c`, boot-arg `linux64net=1`, set by `xnu-run`; `XNU_NET=0` leaves it out) exchanges frames with the
Linux device `xnu0` that `fki.ko` creates. `xnu-net` on the host gives `xnu0` 192.168.77.1, runs dnsmasq (DHCP, DNS forwarding to
`/etc/resolv.conf`) and masquerades everything else with nftables.

configd configures en0 only when it finds it as an Ethernet interface in the registry (`RedwoodEthernet`) and when an `IONetworkStack`
service exists (`MiniIONetworkStack`, otherwise it waits). Verified with build 45913646691: DHCP lease 192.168.77.10, default route via
192.168.77.1, the host pings the phone's iOS.

    wifi-up; XNU_CPUS=4 xnu-run; xnu-net; wifi-join /tmp/wifi.conf

Internet traffic: see below.

## iOS's Wi-Fi (works, 2026-11-27)

By default (`XNU_WIFI=1`) en0 is a radio to iOS: Settings > Wi-Fi lists what the host hears and joins it. `bsd/dev/linux64_wifi.c` answers the
direct port's Apple80211 code (`redwood_apple80211.c`) by sending text lines to `host/initramfs/wifihost`, which drives `wpa_supplicant` and
DHCP on `wlan0`; frames go over `xnu0` and are masqueraded. `launchd` loads `wifid` only when the device tree has `/arm-io/wlan`
(`xnu.ko wlan=1`). `XNU_WIFI=` (empty) gives the wired en0 of above; `XNU_WIFI=fake` offers two made-up networks (BonitoTest, open;
BonitoWPA, password `password123`).

Verified: the list in Settings, a join of the open test network from Settings (check mark, DHCP lease), real scans (8-11 networks reaching
iOS). A real network was joined from Settings on 2026-11-27. Safari did load a page served by the host over this path
(`httpd` on 192.168.77.1, named in the host's `/etc/hosts` for dnsmasq); its content drew black until WebKit was given the GPU (the kernel now writes
the plugin's client list with WebKit's processes); after that the page renders (build 45936681835).

A password typed on the phone passes through RAM files on the host (`/tmp/xnusvc.out`) and `wpa_cli`'s arguments; nothing is stored, so it
is typed again after every boot.

Debugging: `XNU_BOOTARGS="net_names=1 net_trace=60 sweetiolog=configd"`; with `hfsplus` the host can mount the live iOS volume read-only.
