#!/bin/sh
# udhcpc's script: address, default route and name server of the lease
case "$1" in
bound|renew)
	ip addr flush dev "$interface"
	ip addr add "$ip/${mask:-24}" dev "$interface"
	for r in $router; do ip route replace default via "$r" dev "$interface"; break; done
	: > /etc/resolv.conf
	for d in $dns; do echo "nameserver $d" >> /etc/resolv.conf; done ;;
deconfig) ip link set "$interface" up ;;
esac
