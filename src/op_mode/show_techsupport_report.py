#!/usr/bin/env python3
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import os
import sys
from typing import List
from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.utils.process import rc_cmd


def print_header(command: str) -> None:
    """Prints a command with headers '-'.

    Example:

    % print_header('Example command')

    ---------------
    Example command
    ---------------
    """
    header_length = len(command) * '-'
    print(f"\n{header_length}\n{command}\n{header_length}")


def execute_command(command: str, header_text: str) -> None:
    """Executes a command and prints the output with a header.

    Example:
    % execute_command('uptime', "Uptime of the system")

    --------------------
    Uptime of the system
    --------------------
    20:21:57 up  9:04,  5 users,  load average: 0.00, 0.00, 0.0

    """
    print_header(header_text)
    try:
        rc, output = rc_cmd(command)
        # Enable unbuffered print param to improve responsiveness of printed
        # output to end user
        print(output, flush=True)
    # Exit gracefully when user interrupts program output
    # Flush standard streams; redirect remaining output to devnull
    # Resolves T5633: Bug #1 and 3
    except (BrokenPipeError, KeyboardInterrupt):
        os.dup2(os.open(os.devnull, os.O_WRONLY), sys.stdout.fileno())
        sys.exit(1)
    except Exception as e:
        print(f"Error executing command: {command}")
        print(f"Error message: {e}")


def op(cmd: str) -> str:
    """Returns a command with the VyOS operational mode wrapper."""
    return f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {cmd}'


def get_ethernet_interfaces() -> List[Interface]:
    """Returns a list of Ethernet interfaces."""
    return Section.interfaces('ethernet')


def show_version() -> None:
    """Prints the VyOS version and package changes."""
    execute_command(op('show version'), 'VyOS Version and Package Changes')


def show_config_file() -> None:
    """Prints the contents of a configuration file with a header."""
    execute_command('cat /opt/vyatta/etc/config/config.boot', 'Configuration file')


def show_running_config() -> None:
    """Prints the running configuration."""
    execute_command(op('show configuration'), 'Running configuration')


def show_package_repository_config() -> None:
    """Prints the package repository configuration file."""
    execute_command('cat /etc/apt/sources.list', 'Package Repository Configuration File')
    execute_command('ls -l /etc/apt/sources.list.d/', 'Repositories')


def show_user_startup_scripts() -> None:
    """Prints the user startup scripts."""
    execute_command('cat /config/scripts/vyos-preconfig-bootup.script', 'User Startup Scripts (Preconfig)')
    execute_command('cat /config/scripts/vyos-postconfig-bootup.script', 'User Startup Scripts (Postconfig)')


def show_frr_config() -> None:
    """Prints the FRR configuration."""
    execute_command('vtysh -c "show run"', 'FRR configuration')


def show_interfaces() -> None:
    """Prints the interfaces."""
    execute_command(op('show interfaces'), 'Interfaces')


def show_interface_statistics() -> None:
    """Prints the interface statistics."""
    execute_command('ip -s link show', 'Interface statistics')


def show_physical_interface_statistics() -> None:
    """Prints the physical interface statistics."""
    execute_command('/usr/bin/true', 'Physical Interface statistics')
    for iface in get_ethernet_interfaces():
        # Exclude vlans
        if '.' in iface:
            continue
        execute_command(f'ethtool --driver {iface}', f'ethtool --driver {iface}')
        execute_command(f'ethtool --statistics {iface}', f'ethtool --statistics {iface}')
        execute_command(f'ethtool --show-ring {iface}', f'ethtool --show-ring {iface}')
        execute_command(f'ethtool --show-coalesce {iface}', f'ethtool --show-coalesce {iface}')
        execute_command(f'ethtool --pause {iface}', f'ethtool --pause {iface}')
        execute_command(f'ethtool --show-features {iface}', f'ethtool --show-features {iface}')
        execute_command(f'ethtool --phy-statistics {iface}', f'ethtool --phy-statistics {iface}')
    execute_command('netstat --interfaces', 'netstat --interfaces')
    execute_command('netstat --listening', 'netstat --listening')
    execute_command('cat /proc/net/dev', 'cat /proc/net/dev')


def show_bridge() -> None:
    """Show bridge interfaces."""
    execute_command(op('show bridge'), 'Show bridge')


def show_arp() -> None:
    """Prints ARP entries."""
    execute_command(op('show arp'), 'ARP Table (Total entries)')
    execute_command(op('show ipv6 neighbors'), 'show ipv6 neighbors')


def show_route() -> None:
    """Prints routing information."""

    cmd_list_route = [
        "show ip route bgp | head -108",
        "show ip route cache",
        "show ip route connected",
        "show ip route forward",
        "show ip route isis | head -108",
        "show ip route kernel",
        "show ip route ospf | head -108",
        "show ip route rip",
        "show ip route static",
        "show ip route summary",
        "show ip route supernets-only",
        "show ip route table all",
        "show ip route vrf all",
        "show ipv6 route bgp | head -108",
        "show ipv6 route cache",
        "show ipv6 route connected",
        "show ipv6 route forward",
        "show ipv6 route isis",
        "show ipv6 route kernel",
        "show ipv6 route ospfv3",
        "show ipv6 route rip",
        "show ipv6 route static",
        "show ipv6 route summary",
        "show ipv6 route table all",
        "show ipv6 route vrf all",
    ]
    for command in cmd_list_route:
        execute_command(op(command), command)


def show_firewall() -> None:
    """Prints firweall information."""
    execute_command('sudo nft list ruleset', 'nft list ruleset')


def show_system() -> None:
    """Prints system parameters."""
    execute_command(op('show version'), 'Show System Version')
    execute_command(op('show system storage'), 'Show System Storage')
    execute_command(op('show system image details'), 'Show System Image Details')


def show_date() -> None:
    """Print the current date."""
    execute_command('date', 'Current Time')


def show_installed_packages() -> None:
    """Prints installed packages."""
    execute_command('dpkg --list', 'Installed Packages')


def show_loaded_modules() -> None:
    """Prints loaded modules /proc/modules"""
    execute_command('cat /proc/modules', 'Loaded Modules')


def show_cpu_statistics() -> None:
    """Prints CPU statistics."""
    execute_command('/usr/bin/true', 'CPU')
    execute_command('lscpu', 'Installed CPU\'s')
    execute_command('top --iterations 1 --batch-mode --accum-time-toggle', 'Cumulative CPU Time Used by Running Processes')
    execute_command('cat /proc/loadavg', 'Load Average')


def show_system_interrupts() -> None:
    """Prints system interrupts."""
    execute_command('cat /proc/interrupts', 'Hardware Interrupt Counters')


def show_soft_irqs() -> None:
    """Prints soft IRQ's."""
    execute_command('cat /proc/softirqs', 'Soft IRQ\'s')


def show_softnet_statistics() -> None:
    """Prints softnet statistics."""
    execute_command('cat /proc/net/softnet_stat', 'cat /proc/net/softnet_stat')


def show_running_processes() -> None:
    """Prints current running processes"""
    execute_command('ps -ef', 'Running Processes')


def show_memory_usage() -> None:
    """Prints memory usage"""
    execute_command('/usr/bin/true', 'Memory')
    execute_command('cat /proc/meminfo', 'Installed Memory')
    execute_command('free', 'Memory Usage')


def list_disks():
    disks = set()
    with open('/proc/partitions') as partitions_file:
        for line in partitions_file:
            fields = line.strip().split()
            if len(fields) == 4 and fields[3].isalpha() and fields[3] != 'name':
                disks.add(fields[3])
    return disks


def show_storage() -> None:
    """Prints storage information."""
    execute_command('cat /proc/devices', 'Devices')
    execute_command('cat /proc/partitions', 'Partitions')

    for disk in list_disks():
        execute_command(f'fdisk --list /dev/{disk}', f'Partitioning for disk {disk}')


def main():
    # Configuration data
    show_version()
    show_config_file()
    show_running_config()
    show_package_repository_config()
    show_user_startup_scripts()
    show_frr_config()

    # Interfaces
    show_interfaces()
    show_interface_statistics()
    show_physical_interface_statistics()
    show_bridge()
    show_arp()

    # Routing
    show_route()

    # Firewall
    show_firewall()

    # System
    show_system()
    show_date()
    show_installed_packages()
    show_loaded_modules()

    # CPU
    show_cpu_statistics()
    show_system_interrupts()
    show_soft_irqs()
    show_softnet_statistics()

    # Memory
    show_memory_usage()

    # Storage
    show_storage()

    # Processes
    show_running_processes()

    # TODO: Get information from clouds


if __name__ == "__main__":
    main()
