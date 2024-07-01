#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import sys
import json

import vyos.opmode

from vyos.utils.process import cmd

def _get_version_data():
    from vyos.version import get_version_data
    return get_version_data()

def _get_uptime():
    from vyos.utils.system import get_uptime_seconds

    return get_uptime_seconds()

def _get_load_average():
    from vyos.utils.system import get_load_averages

    return get_load_averages()

def _get_cpus():
    from vyos.utils.cpu import get_cpus

    return get_cpus()

def _get_process_stats():
    return cmd('top --iterations 1 --batch-mode --accum-time-toggle')

def _get_storage():
    from vyos.utils.disk import get_persistent_storage_stats

    return get_persistent_storage_stats()

def _get_devices():
    devices = {}
    devices["pci"] = cmd("lspci")
    devices["usb"] = cmd("lsusb")

    return devices

def _get_memory():
    from vyos.utils.file import read_file

    return read_file("/proc/meminfo")

def _get_processes():
    res = cmd("ps aux")

    return res

def _get_interrupts():
    from vyos.utils.file import read_file

    interrupts = read_file("/proc/interrupts")
    softirqs = read_file("/proc/softirqs")

    return (interrupts, softirqs)

def _get_partitions():
    # XXX: as of parted 3.5, --json is completely broken
    # and cannot be used (outputs malformed JSON syntax)
    res = cmd(f"parted --list")

    return res

def _get_running_config():
    from os import getpid
    from vyos.configsession import ConfigSession
    from vyos.utils.strip_config import strip_config_source

    c = ConfigSession(getpid())
    return strip_config_source(c.show_config([]))

def _get_boot_config():
    from vyos.utils.file import read_file
    from vyos.utils.strip_config import strip_config_source

    config = read_file('/opt/vyatta/etc/config.boot.default')

    return strip_config_source(config)

def _get_config_scripts():
    from os import listdir
    from os.path import join
    from vyos.utils.file import read_file

    scripts = []

    dir = '/config/scripts'
    for f in listdir(dir):
        script = {}
        path = join(dir, f)
        data = read_file(path)
        script["path"] = path
        script["data"] = data

        scripts.append(script)

    return scripts

def _get_nic_data():
    from vyos.utils.process import ip_cmd
    link_data = ip_cmd("link show")
    addr_data = ip_cmd("address show")

    return link_data, addr_data

def _get_routes(proto):
    from json import loads
    from vyos.utils.process import ip_cmd

    # Only include complete routing tables if they are not too large
    # At the moment "too large" is arbitrarily set to 1000
    MAX_ROUTES = 1000

    data = {}

    summary = cmd(f"vtysh -c 'show {proto} route summary json'")
    summary = loads(summary)

    data["summary"] = summary

    if summary["routesTotal"] < MAX_ROUTES:
        rib_routes = cmd(f"vtysh -c 'show {proto} route json'")
        data["routes"] = loads(rib_routes)

    if summary["routesTotalFib"] < MAX_ROUTES:
        ip_proto = "-4" if proto == "ip" else "-6"
        fib_routes = ip_cmd(f"{ip_proto} route show")
        data["fib_routes"] = fib_routes

    return data

def _get_ip_routes():
    return _get_routes("ip")

def _get_ipv6_routes():
    return _get_routes("ipv6")

def _get_ospfv2():
    # XXX: OSPF output when it's not configured is an empty string,
    # which is not a valid JSON
    output = cmd("vtysh -c 'show ip ospf json'")
    if output:
        return json.loads(output)
    else:
        return {}

def _get_ospfv3():
    output = cmd("vtysh -c 'show ipv6 ospf6 json'")
    if output:
        return json.loads(output)
    else:
	    return {}

def _get_bgp_summary():
    output = cmd("vtysh -c 'show bgp summary json'")
    return json.loads(output)

def _get_isis():
    output = cmd("vtysh -c 'show isis summary json'")
    if output:
        return json.loads(output)
    else:
        return {}

def _get_arp_table():
    from json import loads
    from vyos.utils.process import cmd

    arp_table = cmd("ip --json -4 neighbor show")
    return loads(arp_table)

def _get_ndp_table():
    from json import loads

    arp_table = cmd("ip --json -6 neighbor show")
    return loads(arp_table)

def _get_nftables_rules():
    nft_rules = cmd("nft list ruleset")
    return nft_rules

def _get_connections():
    from vyos.utils.process import cmd

    return cmd("ss -apO")

def _get_system_packages():
    from re import split
    from vyos.utils.process import cmd

    dpkg_out = cmd(''' dpkg-query -W -f='${Package} ${Version} ${Architecture} ${db:Status-Abbrev}\n' ''')
    pkg_lines = split(r'\n+', dpkg_out)

    # Discard the header, it's five lines long
    pkg_lines = pkg_lines[5:]

    pkgs = []

    for pl in pkg_lines:
        parts = split(r'\s+', pl)
        pkg = {}
        pkg["name"] = parts[0]
        pkg["version"] = parts[1]
        pkg["architecture"] = parts[2]
        pkg["status"] = parts[3]

        pkgs.append(pkg)

    return pkgs

def _get_image_info():
    from vyos.system.image import get_images_details

    return get_images_details()

def _get_kernel_modules():
    from vyos.utils.kernel import lsmod

    return lsmod()

def _get_last_logs(max):
    from systemd import journal

    r = journal.Reader()

    # Set the reader to use logs from the current boot
    r.this_boot()

    # Jump to the last logs
    r.seek_tail()

    # Only get logs of INFO level or more urgent
    r.log_level(journal.LOG_INFO)

    # Retrieve the entries
    entries = []

    # I couldn't find a way to just get last/first N entries,
    # so we'll use the cursor directly.
    num = max
    while num >= 0:
        je = r.get_previous()
        entry = {}

        # Extract the most useful and serializable fields
        entry["timestamp"] = je.get("SYSLOG_TIMESTAMP")
        entry["pid"] = je.get("SYSLOG_PID")
        entry["identifier"] = je.get("SYSLOG_IDENTIFIER")
        entry["facility"] = je.get("SYSLOG_FACILITY")
        entry["systemd_unit"] = je.get("_SYSTEMD_UNIT")
        entry["message"] = je.get("MESSAGE")

        entries.append(entry)

        num = num - 1

    return entries


def _get_raw_data():
    data = {}

    # VyOS-specific information
    data["vyos"] = {}

    ## The equivalent of "show version"
    from vyos.version import get_version_data
    data["vyos"]["version"] = _get_version_data()

    ## Installed images
    data["vyos"]["images"] = _get_image_info()

    # System information
    data["system"] = {}

    ## Uptime and load averages
    data["system"]["uptime"] = _get_uptime()
    data["system"]["load_average"] = _get_load_average()
    data["system"]["process_stats"] = _get_process_stats()

    ## Debian packages
    data["system"]["packages"] = _get_system_packages()

    ## Kernel modules
    data["system"]["kernel"] = {}
    data["system"]["kernel"]["modules"] = _get_kernel_modules()

    ## Processes
    data["system"]["processes"] = _get_processes()

    ## Interrupts
    interrupts, softirqs = _get_interrupts()
    data["system"]["interrupts"] = interrupts
    data["system"]["softirqs"] = softirqs

    # Hardware
    data["hardware"] = {}
    data["hardware"]["cpu"] = _get_cpus()
    data["hardware"]["storage"] = _get_storage()
    data["hardware"]["partitions"] = _get_partitions()
    data["hardware"]["devices"] = _get_devices()
    data["hardware"]["memory"] = _get_memory()

    # Configuration data
    data["vyos"]["config"] = {}

    ## Running config text
    ## We do not encode it so that it's possible to
    ## see exactly what the user sees and detect any syntax/rendering anomalies —
    ## exporting the config to JSON could obscure them
    data["vyos"]["config"]["running"] = _get_running_config()

    ## Default boot config, exactly as in /config/config.boot
    ## It may be different from the running config
    ## _and_ may have its own syntax quirks that may point at bugs
    data["vyos"]["config"]["boot"] = _get_boot_config()

    ## Config scripts
    data["vyos"]["config"]["scripts"] = _get_config_scripts()

    # Network interfaces
    data["network_interfaces"] = {}

    # Interface data from iproute2
    link_data, addr_data = _get_nic_data()
    data["network_interfaces"]["links"] = link_data
    data["network_interfaces"]["addresses"] = addr_data

    # Routing table data
    data["routing"] = {}
    data["routing"]["ip"] = _get_ip_routes()
    data["routing"]["ipv6"] = _get_ipv6_routes()

    # Routing protocols
    data["routing"]["ip"]["ospf"] = _get_ospfv2()
    data["routing"]["ipv6"]["ospfv3"] = _get_ospfv3()

    data["routing"]["bgp"] = {}
    data["routing"]["bgp"]["summary"] = _get_bgp_summary()

    data["routing"]["isis"] = _get_isis()

    # ARP and NDP neighbor tables
    data["neighbor_tables"] = {}
    data["neighbor_tables"]["arp"] = _get_arp_table()
    data["neighbor_tables"]["ndp"] = _get_ndp_table()

    # nftables config
    data["nftables_rules"] = _get_nftables_rules()

    # All connections
    data["connections"] = _get_connections()

    # Logs
    data["last_logs"] = _get_last_logs(1000)

    return data

def show(raw: bool):
    data = _get_raw_data()
    if raw:
        return data
    else:
        raise vyos.opmode.UnsupportedOperation("Formatted output is not implemented yet")

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
    except (KeyboardInterrupt, BrokenPipeError):
        sys.exit(1)
