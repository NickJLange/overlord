#!/usr/bin/bash 

### Generate IP Tables rules to protect the host from bad people
sleep $(( $RANDOM%2 + 1))m
### whitelist private networks
iptables -F INPUT
iptables -A INPUT -s 192.168.0.0/16 -j ACCEPT
iptables -A INPUT -s 172.16.0.0/12 -j ACCEPT
iptables -A INPUT -s 10.0.0.0/8 -j ACCEPT
iptables -A INPUT -s newyork.nicklange.family -j ACCEPT
iptables -A INPUT -s miyagi.nicklange.family -j ACCEPT
iptables -A INPUT -s wisconsin.nicklange.family -j ACCEPT
iptables -A INPUT -s eva.nicklange.family -j ACCEPT
iptables -A INPUT -p udp -j ACCEPT
iptables -A INPUT -p tcp --dport 22  -j DROP


ip6tables -F INPUT
ip6tables -A INPUT -s fd::0/8 -j ACCEPT
ip6tables -A INPUT -p udp -j ACCEPT
ip6tables -A INPUT -p tcp --dport 22  -j DROP
