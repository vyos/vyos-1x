#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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
import argparse
from pathlib import Path
from dataclasses import dataclass
from dataclasses import field
from typing import Callable
from typing import Optional
from typing import Sequence

from vyos.ifconfig import Section
from vyos.ifconfig import Interface
from vyos.utils.process import rc_cmd
from vyos.utils.process import wrap_op as op


@dataclass(frozen=True)
class BaseSpec:
    # Available only for 'show tech-support report' (not 'generate tech-support archive')
    report_only: Optional[bool] = field(kw_only=True, default=False)


@dataclass(frozen=True)
class CommandSpec(BaseSpec):
    header: str  # Display header for a command section
    command: str  # Shell command to execute


@dataclass(frozen=True)
class FuncSpec(BaseSpec):
    name: str  # Display name for a function section
    fn: Callable[
        ['Runner'], None
    ]  # Callable that receives a Runner and writes output via it


class OutputSink:
    """Writes output to stdout and/or a file, depending on parameters"""

    def __init__(self, *, file_path: Optional[Path]):
        # Target file path; None means stdout
        self._file_path = file_path
        self._fh = None

    def __enter__(self) -> 'OutputSink':
        # Open output file if not writing to stdout
        if not self.is_stdout:
            self._file_path.parent.mkdir(parents=True, exist_ok=True)
            # Use text mode, overwrite per run
            self._fh = self._file_path.open('w', encoding='utf-8', errors='replace')
        return self

    def __exit__(self, exc_type, exc, tb):
        if self._fh is not None:
            self._fh.close()
            self._fh = None

    @property
    def is_stdout(self):
        # True when output is directed to stdout
        return self._file_path is None

    def write(self, text: str):
        # Enable unbuffered print param to improve responsiveness of printed
        # output to end user
        if self.is_stdout:
            print(text, end='', flush=True)
        else:
            if self._fh is not None:
                self._fh.write(text)
                self._fh.flush()


class Runner:
    """Executes commands and writes output to the provided sink"""

    def __init__(self, sink: OutputSink):
        self.sink = sink

    def exec(self, command: str, header: str = None):
        texts = []

        if header:
            texts.append(header)
        texts.append(f'Command: {command}')

        try:
            # Start a new section for this command
            self.section('\n'.join(texts))

            rc, output = rc_cmd(command)
            # Ensure output ends with newline when present
            if output and not output.endswith('\n'):
                output += '\n'

            self.sink.write(output)
            if rc not in (0, None):
                self.sink.write(
                    f'Command `{command}` returned non-zero ({rc}) exit status\n'
                )
        except (BrokenPipeError, KeyboardInterrupt):
            raise
        except Exception as e:
            self.sink.write(f'Error executing command: {command}\n')
            self.sink.write(f'Error message: {e}\n')

    def section(self, title: str):
        """Just print a section header without running a command"""
        self.sink.write(header_block(title))


def header_block(title: str, delimiter='-') -> str:
    """Create an underline/overline header block for multiline text."""
    lines = title.splitlines()
    max_len = max(len(line) for line in lines)
    line = delimiter * max_len
    title_block = '\n'.join(lines)
    return f'\n{line}\n{title_block}\n{line}\n'


def select_reports(args: argparse.Namespace) -> dict[str, tuple[BaseSpec]]:
    reports = REPORTS.copy()
    requested = args.reports

    if requested:
        missing = [r for r in requested if r not in reports]
        if missing:
            known = ', '.join(sorted(reports.keys()))
            raise SystemExit(f'Unknown report(s): {", ".join(missing)}. Known: {known}')

        reports = {name: reports[name] for name in requested}

    if args.launched_from_generate_archive:
        for key in reports.keys():
            items = reports[key]
            reports[key] = {item for item in items if not item.report_only}

    return reports


def execute_item(item: BaseSpec, runner: Runner) -> None:
    if isinstance(item, CommandSpec):
        runner.exec(item.command, item.header)
    elif isinstance(item, FuncSpec):
        runner.section(item.name)
        item.fn(runner)
    else:
        assert False, f'Unsupported report type: {type(item)}'


def parse_args(argv: Sequence[str]) -> argparse.Namespace:
    p = argparse.ArgumentParser(description='VyOS tech-support command collector')
    p.add_argument(
        '--outdir',
        type=Path,
        default=None,
        help=(
            'Directory to write report files into (one file per report group). '
            'If this option is omitted, files are written to stdout.'
        ),
    )
    p.add_argument(
        '--reports',
        nargs='*',
        default=[],
        help=(
            'Which report groups to run (default: all). '
            'Example: --reports vyos-main-info'
        ),
    )
    p.add_argument(
        '--launched-from-generate-archive',
        action='store_true',
        default=False,
        help=(
            'A boolean flag indicates that command executed for generating '
            'tech-support archive (`generate tech-support archive`). '
            'In this case some sections will be ignored because already available in archive.'
        ),
    )
    return p.parse_args(argv)


def main(argv: Sequence[str]):
    args = parse_args(argv)

    # Select which reports to execute
    chosen = select_reports(args)

    # Execute each report and write to its own sink
    for report_name, commands in chosen.items():
        # Use a per-report output file when `outdir` is provided
        file_path = (args.outdir / report_name) if args.outdir else None

        with OutputSink(file_path=file_path) as sink:
            runner = Runner(sink)
            try:
                # Write top-level report header
                sink.write(header_block(report_name, delimiter='='))

                # Execute each item in the report
                for item in commands:
                    execute_item(item, runner)
            except (BrokenPipeError, KeyboardInterrupt):
                if sink.is_stdout:
                    # Exit gracefully when user interrupts program output
                    # Flush standard streams; redirect remaining output to devnull
                    # Resolves T5633: Bug #1 and 3
                    os.dup2(
                        os.open(os.devnull, os.O_WRONLY),
                        sys.stdout.fileno(),  # pylint: disable = no-member
                    )
                sys.exit(1)


def get_ethernet_interfaces() -> list[Interface]:
    """Returns a list of Ethernet interfaces."""
    return Section.interfaces('ethernet')


def show_physical_interface_statistics(r: Runner):
    """Prints the physical interface statistics."""

    for iface in get_ethernet_interfaces():
        if '.' in iface:  # exclude VLANs
            continue

        r.exec(f'ethtool --driver {iface}')
        r.exec(f'ethtool --statistics {iface}')
        r.exec(f'ethtool --show-ring {iface}')
        r.exec(f'ethtool --show-coalesce {iface}')
        r.exec(f'ethtool --pause {iface}')
        r.exec(f'ethtool --show-features {iface}')
        r.exec(f'ethtool --phy-statistics {iface}')
        r.exec(f'ethtool --module-info {iface}')

    for path in Path('/run/udev/vyos').glob('*'):
        if path.is_file():
            r.exec(f'cat {path.resolve()}')


def _exec_list_op(r: Runner, commands: list):
    for command in commands:
        r.exec(op(command))


def show_route(r: Runner):
    """Prints routing information."""

    commands = [
        'show ip route bgp | head -108',
        'show ip route connected',
        'show ip route forward | head -108',
        'show ip route isis | head -108',
        'show ip route kernel',
        'show ip route ospf | head -108',
        'show ip route rip | head -108',
        'show ip route static',
        'show ip route summary',
        'show ip route supernets-only | head -108',
        'show ip route table all | head -108',
        'show ip route vrf all | head -108',
        'show ipv6 route bgp | head -108',
        'show ipv6 route connected',
        'show ipv6 route forward | head -108',
        'show ipv6 route isis | head -108',
        'show ipv6 route kernel',
        'show ipv6 route ospfv3 | head -108',
        'show ipv6 route rip | head -108',
        'show ipv6 route static',
        'show ipv6 route summary',
        'show ipv6 route table all | head -108',
        'show ipv6 route vrf all | head -108',
    ]
    _exec_list_op(r, commands)


def show_evpn(r: Runner):
    """Prints EVPN information."""

    commands = [
        'show evpn mac vni all',
        'show evpn next-hops vni all',
        'show evpn rmac vni all',
        'show evpn access-vlan',
        'show evpn arp-cache vni all',
        'show evpn es',
        'show evpn es-evi',
    ]
    _exec_list_op(r, commands)


def show_mpls(r: Runner):
    """Prints MPLS information."""

    commands = [
        'show mpls pseudowire',
        'show mpls table',
        'show mpls ldp binding',
        'show mpls ldp discovery',
        'show mpls ldp interface',
        'show mpls ldp neighbor',
    ]
    _exec_list_op(r, commands)


def show_rpki(r: Runner):
    """Prints RPKI information."""

    commands = [
        'show rpki cache-server',
        'show rpki cache-connection',
    ]
    _exec_list_op(r, commands)


def _list_disks():
    disks = set()
    with open('/proc/partitions') as partitions_file:
        for line in partitions_file:
            fields = line.strip().split()
            if len(fields) == 4 and fields[3].isalpha() and fields[3] != 'name':
                disks.add(fields[3])
    return disks


def show_storage(r: Runner):
    """Prints storage information."""

    r.exec('cat /proc/mounts', 'Mount table')
    r.exec('cat /proc/partitions', 'Partitions table')

    for disk in _list_disks():
        r.exec(f'fdisk --list /dev/{disk}', f'Partitioning for disk {disk}')

    r.exec('df -ah', 'Filesystem usage')
    r.exec('df -ahi', 'Filesystem inode usage')


def show_kernel_interface_counters(r: Runner):
    """Prints kernel network interface counters by fixed format."""

    headers = (
        'bytes',
        'packets',
        'errs',
        'drop',
        'fifo',
        'frame',
        'compressed',
        'multicast',
    )
    new_headers = (
        ['Interface'] + [f'RX-{h}' for h in headers] + [f'TX-{h}' for h in headers]
    )
    echo_template = ' '.join(new_headers)
    awk_template = ','.join([f'${i}' for i in range(1, len(new_headers) + 1)])

    cmd = (
        """(echo "{0}" && awk 'NR>2 {{print {1}}}' /proc/net/dev) | column -t""".format(
            echo_template, awk_template
        )
    )
    r.exec(cmd, 'cat /proc/net/dev | column -t')


REPORTS: dict[str, tuple[BaseSpec]] = {
    'vyos-main-info': (
        CommandSpec('VyOS version and package info', op('show version')),
        CommandSpec(
            'Running configuration (commands)', op('show configuration commands')
        ),
        CommandSpec('Running configuration (structured)', op('show configuration')),
        CommandSpec(
            'Configuration file (config.boot)',
            'cat /opt/vyatta/etc/config/config.boot',
            report_only=True,  # Ignored because already exists in 'tech-support archive'
        ),
        CommandSpec('Interfaces summary', op('show interfaces')),
        CommandSpec('Bridge status', op('show bridge')),
        CommandSpec('ARP table', op('show arp')),
        CommandSpec('IPv6 neighbor table', op('show ipv6 neighbors')),
        CommandSpec('System storage overview', op('show system storage')),
        CommandSpec('Installed images details', op('show system image details')),
        CommandSpec(
            'User startup script (preconfig)',
            'cat /config/scripts/vyos-preconfig-bootup.script',
            report_only=True,
        ),
        CommandSpec(
            'User startup script (postconfig)',
            'cat /config/scripts/vyos-postconfig-bootup.script',
            report_only=True,
        ),
    ),
    'routing-info': (
        FuncSpec('Routing table (IPv4/IPv6)', show_route),
        CommandSpec('BFD peers', op('show bfd peers')),
        FuncSpec('EVPN status', show_evpn),
        FuncSpec('MPLS status', show_mpls),
        FuncSpec('RPKI status', show_rpki),
    ),
    'frr-info': (
        CommandSpec('FRR running configuration', 'vtysh -c "show running-config"'),
        CommandSpec('FRR memory usage', 'vtysh -c "show memory"'),
        CommandSpec('FRR work queues', 'vtysh -c "show work-queues"'),
        CommandSpec('FRR IPv4 nexthop tracking (NHT)', 'vtysh -c "show ip nht"'),
        CommandSpec('FRR IPv6 nexthop tracking (NHT)', 'vtysh -c "show ipv6 nht"'),
        CommandSpec('FRR DMVPN status', 'vtysh -c "show dmvpn"'),
        CommandSpec('FRR event CPU stats', 'vtysh -c "show event cpu"'),
        CommandSpec('FRR event poll stats', 'vtysh -c "show event poll"'),
        CommandSpec('FRR event timers', 'vtysh -c "show event timers"'),
        CommandSpec(
            'FRR SRv6 locator',
            'vtysh -c "show segment-routing srv6 locator"',
        ),
        CommandSpec(
            'FRR SRv6 manager',
            'vtysh -c "show segment-routing srv6 manager"',
        ),
    ),
    'proc-and-sysctl-info': (
        CommandSpec('System load average', 'cat /proc/loadavg'),
        FuncSpec('Kernel network interface counters', show_kernel_interface_counters),
        CommandSpec('Loaded kernel modules', 'cat /proc/modules'),
        CommandSpec('Hardware interrupt counters', 'cat /proc/interrupts'),
        CommandSpec('SoftIRQ counters', 'cat /proc/softirqs'),
        CommandSpec('Softnet statistics', 'cat /proc/net/softnet_stat'),
        CommandSpec('Memory info', 'cat /proc/meminfo'),
        CommandSpec(
            'NUMA node memory info',
            'cat /sys/devices/system/node/node*/meminfo',
        ),
        CommandSpec('VM statistics', 'cat /proc/vmstat'),
        CommandSpec('Registered character/block devices', 'cat /proc/devices'),
        CommandSpec('Kernel command line', 'cat /proc/cmdline'),
        CommandSpec('All sysctl values', 'sysctl -a'),
    ),
    'net-and-processes-info': (
        CommandSpec('Network interfaces', 'netstat --interfaces'),
        CommandSpec('Listening sockets', 'netstat --listening'),
        CommandSpec('Socket summary', 'ss -s'),
        CommandSpec('All sockets with details', 'ss -a -e -m -p'),
        CommandSpec('Full process listing', 'ps -eF'),
    ),
    'ethtool-info': (
        CommandSpec(
            'Link details and interface counters',
            'ip -s -d link show',
        ),
        FuncSpec('Physical interface statistics', show_physical_interface_statistics),
    ),
    'lspci-and-numa-info': (
        CommandSpec('PCI devices', 'lspci -knnv'),
        CommandSpec('', 'numactl --hardware'),
        CommandSpec('', 'numastat -cm'),
    ),
    'nftables-info': (
        CommandSpec('nftables ruleset', 'nft list ruleset'),
        CommandSpec('VyOS firewall configuration', op('show firewall')),
        CommandSpec('VyOS firewall zone policy', op('show firewall zone-policy')),
    ),
    'dpkg-and-modules-info': (
        CommandSpec('Installed packages', 'dpkg --list'),
        CommandSpec(
            'Diff dpkg status (image vs running system)',
            'diff /usr/lib/live/mount/rootfs/*.squashfs/var/lib/dpkg/status /var/lib/dpkg/status',
        ),
        CommandSpec('APT sources list', 'cat /etc/apt/sources.list'),
        CommandSpec(
            'APT sources.d directory listing', 'ls -l /etc/apt/sources.list.d/'
        ),
        CommandSpec('Loaded kernel modules', 'lsmod'),
    ),
    'system-resources-info': (
        CommandSpec('Current time (date)', 'date'),
        CommandSpec('CPU information', 'lscpu'),
        CommandSpec(
            'Per-process cumulative CPU usage snapshot (top batch, accumulated)',
            'top --iterations 1 --batch-mode --accum-time-toggle',
        ),
        CommandSpec('atop snapshot (CPU view)', 'atop -a -y -1 -c -g -C 1 1 | tee'),
        CommandSpec('atop snapshot (memory view)', 'atop -a -y -1 -c -m -M 1 1 | tee'),
        CommandSpec('atop snapshot (disk view)', 'atop -a -y -1 -c -d -D 1 1 | tee'),
        CommandSpec('atop snapshot (network view)', 'atop -a -y -1 -c -n -N 1 1 | tee'),
        CommandSpec('Memory usage', 'free -lhv'),
        FuncSpec('Storage overview', show_storage),
    ),
    'ipsec-debug-info': (
        CommandSpec('strongSwan connections', 'swanctl -L'),
        CommandSpec('strongSwan loaded connections', 'swanctl -l'),
        CommandSpec('strongSwan policies', 'swanctl -P'),
        CommandSpec('XFRM security associations', 'ip x sa show'),
        CommandSpec('XFRM policies', 'ip x policy show'),
        CommandSpec('XFRM state', 'ip xfrm state'),
        CommandSpec('Tunnels', 'ip tunnel show'),
        CommandSpec('Addresses', 'ip address'),
        CommandSpec('Policy routing rules', 'ip rule show'),
        CommandSpec('Routes', 'ip route | head -100'),
        CommandSpec('Routes from table 220', 'ip route show table 220'),
    ),
    'vpp-info': (
        CommandSpec('', 'cat /run/vpp/vpp.conf'),
        CommandSpec('', 'vppctl show version verbose cmdline'),
        CommandSpec('', 'vppctl show hardware-interfaces'),
        CommandSpec('', 'vppctl show interface address'),
        CommandSpec('', 'vppctl show interface'),
        CommandSpec('', 'vppctl show errors'),
        CommandSpec('', 'vppctl show runtime'),
        CommandSpec(
            '',
            'vppctl show memory api-segment stats-segment numa-heaps main-heap map verbose',
        ),
        CommandSpec('', 'vppctl show buffers'),
        CommandSpec('', 'vppctl show physmem detail'),
        CommandSpec('', 'vppctl show physmem map'),
        CommandSpec('', 'vppctl show cpu'),
        CommandSpec('', 'vppctl show threads'),
        CommandSpec('', 'vppctl show node counters'),
        CommandSpec('', 'vppctl show l2fib'),
        CommandSpec('', 'vppctl show bridge-domain'),
        CommandSpec('', 'vppctl show ip fib | head -100'),
        CommandSpec('', 'vppctl show ip neighbors'),
        CommandSpec('', 'vppctl show ip6 fib | head -100'),
        CommandSpec('', 'vppctl show ip6 neighbors'),
        CommandSpec('', 'vppctl show mpls fib'),
        CommandSpec('', 'vppctl show mpls tunnel'),
        CommandSpec('', 'vppctl show trace'),
    ),
}


if __name__ == '__main__':
    main(sys.argv[1:])
