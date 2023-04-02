#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from vyos.util import call
import os


def header(cmd):
    print(16 * '-' + '\n' + cmd + '\n' + 16 * '-')
    return


# get intefaces info
interfaces_list = os.popen('ls /sys/class/net/ | grep eth').read().split()
bridges_list = os.popen('ls /sys/class/net/ | grep br').read().split()

###################### THE PART OF CONFIGURATION ######################

cmd_list_conf = [
    "VyOS Version and Package Changes%/opt/vyatta/bin/vyatta-op-cmd-wrapper show version all",
    "Configuration File%cat /opt/vyatta/etc/config/config.boot",
    "Running configuration%/opt/vyatta/bin/vyatta-op-cmd-wrapper show configuration",
    "Package Repository Configuration File%cat /etc/apt/sources.list",
    "User Startup Scripts%cat /etc/rc.local",
    "Quagga Configuration%vtysh -c 'show run'"
]


def CONFIGURATION(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        head = line[0]
        command = line[1]
        header(head)
        call(command)
    return


###################### THE PART OF INTERFACES ######################

cmd_list_int = [
    "Interfaces%/opt/vyatta/bin/vyatta-op-cmd-wrapper show interfaces",
    "Ethernet",
    "Interface statistics%ip -s link show",
    "Physical Interface statistics for%ethtool -S",
    "Physical Interface Details for %/opt/vyatta/bin/vyatta-op-cmd-wrapper show interfaces ethernet%ethtool -k $eth",
    "ARP Table (Total entries)%/opt/vyatta/bin/vyatta-op-cmd-wrapper show arp",
    "Number of incomplete entries in ARP table%show arp | grep incomplete | wc -l",
    "Bridges"
]


def INTERFACES(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        head = line[0]
        if command_line.startswith("Ethernet"):
            header(command_line)
        elif command_line.startswith("Physical Interface statistics"):
            for command_interface in interfaces_list:
                header(f'{head} {command_interface}')
                call(f'{line[1]} {command_interface}')
        elif command_line.startswith("Physical Interface Details"):
            for command_interface in interfaces_list:
                header(f'{head} {command_interface}')
                call(f'{line[1]} {command_interface} physical')
                call(f'{line[2]} {command_interface}')
        elif command_line.startswith("Bridges"):
            header(command_line)
            for command_interface in bridges_list:
                header(f'Information for {command_interface}')
                call(f'/sbin/brctl showstp {command_interface}')
                call(f'/sbin/brctl showmacs {command_interface}')
        else:
            command = line[1]
            header(head)
            call(command)
    return


###################### THE PART OF ROUTING ######################

cmd_list_route = [
    "show ip route bgp",
    "show ip route cache",
    "show ip route connected",
    "show ip route forward",
    "show ip route isis",
    "show ip route kernel",
    "show ip route ospf",
    "show ip route rip",
    "show ip route static",
    "show ip route summary",
    "show ip route supernets-only",
    "show ip route table",
    "show ip route tag",
    "show ip route vrf",
    "show ipv6 route bgp",
    "show ipv6 route cache",
    "show ipv6 route connected",
    "show ipv6 route forward",
    "show ipv6 route isis",
    "show ipv6 route kernel",
    "show ipv6 route ospf",
    "show ipv6 route rip",
    "show ipv6 route static",
    "show ipv6 route summary",
    "show ipv6 route supernets-only",
    "show ipv6 route table",
    "show ipv6 route tag",
    "show ipv6 route vrf",
]


def ROUTING(cmd):
    for command_line in cmd:
        head = command_line
        command = command_line
        header(head)
        call(f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {command}')
    return


###################### THE PART OF IPTABLES ######################

cmd_list_iptables = [
    "Filter Chain Details%sudo /sbin/iptables -L -vn",
    "Nat Chain Details%sudo /sbin/iptables -t nat -L -vn",
    "Mangle Chain Details%sudo /sbin/iptables -t mangle -L -vn",
    "Raw Chain Details%sudo /sbin/iptables -t raw -L -vn",
    "Save Iptables Rule-Set%sudo iptables-save -c"
]


def IPTABLES(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        head = line[0]
        command = line[1]
        header(head)
        call(command)
    return


###################### THE PART OF SYSTEM ######################

cmd_list_system = [
    "Show System Image Version%show system image version",
    "Show System Image Storage%show system image storage",
    "Current Time%date",
    "Installed Packages%dpkg -l",
    "Loaded Modules%cat /proc/modules",
    "CPU",
    "Installed CPU/s%lscpu",
    "Cumulative CPU Time Used by Running Processes%top -n1 -b -S",
    "Hardware Interrupt Counters%cat /proc/interrupts",
    "Load Average%cat /proc/loadavg"
]


def SYSTEM(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        head = line[0]
        if command_line.startswith("CPU"):
            header(command_line)
        elif line[1].startswith("show"):
            header(head)
            command = line[1]
            call(f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {command}')
        else:
            header(head)
            command = line[1]
            call(command)
    return


###################### THE PART OF PROCESSES ######################

cmd_list_processes = [
    "Running Processes%ps -ef",
    "Memory",
    "Installed Memory%cat /proc/meminfo",
    " Memory Usage%free",
    "Storage",
    "Devices%cat /proc/devices",
    "Partitions%cat /proc/partitions",
    "Partitioning for disks%fdisk -l /dev/"
]


def PROCESSES(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        head = line[0]
        if command_line.startswith("Memory"):
            header(command_line)
        elif command_line.startswith("Storage"):
            header(command_line)
        elif command_line.startswith("Partitioning for disks"):
            header(head)
            disks = set()
            with open('/proc/partitions') as partitions_file:
                for line in partitions_file:
                    fields = line.strip().split()
                    if len(fields) == 4 and fields[3].isalpha() and fields[3] != 'name':
                        disks.add(fields[3])
                for disk in disks:
                    call(f'fdisk -l /dev/{disk}')
        else:
            header(head)
            command = line[1]
            call(command)
    return


###################### THE PART OF CORE SECTION ######################

cmd_list_core = [
    "Mounts%cat /proc/mounts",
    "Diskstats%cat /proc/diskstats",
    "Hard Drive Usage%df -h -x squashfs",
    # "General System",
    "Boot Messages%cat /var/log/dmesg",
    "Recent Kernel messages (dmesg)%dmesg",
    "PCI Info%sudo lspci -vvx",
    "PCI Vendor and Device Codes%sudo lspci -nn",
    # "System Info%${vyatta_bindir}/vyatta-show-dmi",
    "GRUB Command line%cat /proc/cmdline",
    "Open Ports%sudo lsof -P -n -i",
    "System Startup Files%ls -l /etc/rc?.d",
    "Login History%last -ix",
    "Recent Log Messages%tail -n 250 /var/log/messages",
    "NTP%/opt/vyatta/bin/vyatta-op-cmd-wrapper show ntp",
]


def CORE(cmd):
    for command_line in cmd:
        line = command_line.split('%')
        command = line[1]
        header(line[0])
        call(command)
    return


###################### THE PART OF VyOS INFORMATION ######################

cmd_list_vyos = [
    "BGP",
    "header BGP Summary",
    "show ip bgp summary",
    "header BGP Neighbors",
    "show ip bgp neighbors",
    "header BGP Debugging Information",
    "show monitoring protocols bgp",
    "CLUSTERING",
    "Cluster Status",
    "show cluster status",
    "DHCP Server",
    "DHCP Leases",
    "show dhcp server leases",
    "DHCP Statistics",
    "show dhcp server statistics",
    "DHCP Client",
    "DHCP Client Leases",
    "show dhcp client leases",
    "DHCPV6 Server",
    "DHCPV6 Server Status",
    "show dhcpv6 server status",
    "DHCPV6 Server Leases",
    "show dhcpv6 server leases",
    "DHCPV6 Relay",
    "DHCPV6 Relay Status",
    "show dhcpv6 relay-agent status",
    "DHCPV6 Client",
    "DHCPV6 Client Leases",
    "show dhcpv6 client leases",
    "DNS",
    "DNS Dynamic Status",
    "show dns dynamic status",
    "DNS Forwarding Statistics",
    "show dns forwarding statistics",
    "DNS Forwarding Nameservers",
    "show dns forwarding nameservers",
    "FIREWALL",
    "Firewall Group",
    "show firewall group",
    "Firewall Summary",
    "show firewall summary",
    "Firewall Statistics",
    "show firewall statistics",
    "IPSec",
    "IPSec Status",
    "show vpn ipsec status",
    "IPSec sa",
    "show vpn ipsec sa",
    "IPSec sa Detail",
    "show vpn ipsec sa detail",
    "IPSec sa Statistics",
    "show vpn ipsec sa statistics",
    "/etc/ipsec.conf",
    "cat /etc/ipsec.conf",
    "/etc/ipsec.secrets",
    "cat /etc/ipsec.secrets",
    "NAT",
    "NAT Rules",
    "show nat rules",
    "NAT Statistics",
    "show nat statistics",
    "NAT Translations Detail",
    "show nat translations detail",
    "FlowAccounting",
    "show flow-accounting",
    "OPENVPN",
    "OpenVPN Interfaces",
    "show interfaces openvpn detail",
    "OpenVPN Server Status",
    "show openvpn status server",
    "OSPF",
    "OSPF Neighbor",
    "show ip ospf neighbor",
    "OSPF Route",
    "show ip ospf route",
    "OSPF Debugging Information",
    "show monitoring protocols ospf",
    "OSPFV3",
    "OSPFV3 Debugging Information",
    "show monitoring protocols ospfv3",
    "Policy",
    "IP Route Maps",
    "show ip protocol",
    "Route-Map",
    "show route-map",
    # header IP Access Lists
    # show ip access-lists
    "IP Community List",
    "show ip community-list",
    "Traffic Policy",
    "Current Traffic Policies",
    "show queueing",
    "RIP",
    "IP RIP",
    "show ip rip",
    "RIP Status",
    "show ip rip status",
    "RIP Debugging Information",
    "show monitoring protocols rip",
    "RIPNG",
    "RIPNG Debugging Information",
    "show monitoring protocols ripng",
    "VPN-L2TP",
    "VPN ike secrets",
    "show vpn ike secrets",
    "VPN rsa-keys",
    "show vpn ike rsa-keys",
    "VPN ike sa",
    "show vpn ike sa",
    "VPN ike Status",
    "show vpn ike status",
    "VPN Remote-Access",
    "show vpn remote-access",
    "VPN Debug Detail",
    "show vpn debug detail",
    "VPN-PPTP",
    "VPN Remote-Access",
    "show vpn remote-access",
    "VRRP",
    # XXX: not checking if configured, we'd have to walk all VIFs
    "show vrrp detail",
    "WAN LOAD BALANCING",
    "Wan Load Balance",
    "show wan-load-balance",
    "Wan Load Balance Status",
    "show wan-load-balance status",
    "Wan Load Balance Connection",
    "show wan-load-balance connection",
    "WEBPROXY/URL-FILTERING",
    "WebProxy Blacklist Categories",
    "show webproxy blacklist categories",
    "WebProxy Blacklist Domains",
    "show webproxy blacklist domains",
    "WebProxy Blacklist URLs",
    "show webproxy blacklist urls",
    "WebProxy Blacklist Log",
    "show webproxy blacklist log summary",
]


def VyOS(cmd):
    for command_line in cmd:
        if command_line.startswith("show"):
            call(f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {command_line}')
        elif command_line.startswith("cat"):
            call(command_line)
        else:
            header(command_line)
    return


###################### execute all the commands ######################

header('CONFIGURATION')
CONFIGURATION(cmd_list_conf)

header('INTERFACES')
INTERFACES(cmd_list_int)

header('ROUTING')
ROUTING(cmd_list_route)

header('IPTABLES')
IPTABLES(cmd_list_iptables)

header('SYSTEM')
SYSTEM(cmd_list_system)

header('PROCESSES')
PROCESSES(cmd_list_processes)

header('CORE')
CORE(cmd_list_core)

header('VyOS Information')
VyOS(cmd_list_vyos)
