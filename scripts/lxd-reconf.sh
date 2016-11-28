#!/usr/bin/expect

spawn dpkg-reconfigure -freadline -p medium lxd

expect "Would you like to setup a network bridge for LXD containers now?"
send "yes\r"
expect "Bridge interface name:"
send "lxdbr0\r"
expect "Do you want to setup an IPv4 subnet?"
send "yes\r"
expect "IPv4 address:"
send "10.0.8.1\r"
expect "IPv4 CIDR mask:"
send "24\r"
expect "First DHCP address:"
send "10.0.8.2\r"
expect "Last DHCP address:"
send "10.0.8.254\r"
expect "Max number of DHCP clients:"
send "250\r"
expect "Do you want to NAT the IPv4 traffic?"
send "yes\r"
expect "Do you want to setup an IPv6 subnet?"
send "no\r"

# done
expect eof