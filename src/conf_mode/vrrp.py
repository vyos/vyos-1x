#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import subprocess

from sys import exit
from ipaddress import ip_address, ip_interface, IPv4Interface, IPv6Interface, IPv4Address, IPv6Address
from jinja2 import FileSystemLoader, Environment
from json import dumps
from pathlib import Path

import vyos.config
import vyos.keepalived

from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError

daemon_file = "/etc/default/keepalived"
config_file = "/etc/keepalived/keepalived.conf"
config_dict_path = "/run/keepalived_config.dict"

def get_config():
    vrrp_groups = []
    sync_groups = []

    config = vyos.config.Config()

    # Get the VRRP groups
    for group_name in config.list_nodes("high-availability vrrp group"):
        config.set_level("high-availability vrrp group {0}".format(group_name))

        # Retrieve the values
        group = {"preempt": True, "use_vmac": False, "disable": False}

        if config.exists("disable"):
            group["disable"] = True

        group["name"] = group_name
        group["vrid"] = config.return_value("vrid")
        group["interface"] = config.return_value("interface")
        group["description"] = config.return_value("description")
        group["advertise_interval"] = config.return_value("advertise-interval")
        group["priority"] = config.return_value("priority")
        group["hello_source"] = config.return_value("hello-source-address")
        group["peer_address"] = config.return_value("peer-address")
        group["sync_group"] = config.return_value("sync-group")
        group["preempt_delay"] = config.return_value("preempt-delay")
        group["virtual_addresses"] = config.return_values("virtual-address")

        group["auth_password"] = config.return_value("authentication password")
        group["auth_type"] = config.return_value("authentication type")

        group["health_check_script"] = config.return_value("health-check script")
        group["health_check_interval"] = config.return_value("health-check interval")
        group["health_check_count"] = config.return_value("health-check failure-count")

        group["master_script"] = config.return_value("transition-script master")
        group["backup_script"] = config.return_value("transition-script backup")
        group["fault_script"] = config.return_value("transition-script fault")
        group["stop_script"] = config.return_value("transition-script stop")

        if config.exists("no-preempt"):
            group["preempt"] = False
        if config.exists("rfc3768-compatibility"):
            group["use_vmac"] = True

        # Substitute defaults where applicable
        if not group["advertise_interval"]:
            group["advertise_interval"] = 1
        if not group["priority"]:
            group["priority"] = 100
        if not group["preempt_delay"]:
            group["preempt_delay"] = 0
        if not group["health_check_interval"]:
            group["health_check_interval"] = 60
        if not group["health_check_count"]:
            group["health_check_count"] = 3

        # FIXUP: translate our option for auth type to keepalived's syntax
        # for simplicity
        if group["auth_type"]:
            if group["auth_type"] == "plaintext-password":
                group["auth_type"] = "PASS"
            else:
                group["auth_type"] = "AH"

        vrrp_groups.append(group)

    config.set_level("")

    # Get the sync group used for conntrack-sync
    conntrack_sync_group = None
    if config.exists("service conntrack-sync failover-mechanism vrrp"):
        conntrack_sync_group = config.return_value("service conntrack-sync failover-mechanism vrrp sync-group")

    # Get the sync groups
    for sync_group_name in config.list_nodes("high-availability vrrp sync-group"):
        config.set_level("high-availability vrrp sync-group {0}".format(sync_group_name))

        sync_group = {"conntrack_sync": False}
        sync_group["name"] = sync_group_name
        sync_group["members"] = config.return_values("member")
        if conntrack_sync_group:
            if conntrack_sync_group == sync_group_name:
                sync_group["conntrack_sync"] = True

        # add transition script configuration
        sync_group["master_script"] = config.return_value("transition-script master")
        sync_group["backup_script"] = config.return_value("transition-script backup")
        sync_group["fault_script"] = config.return_value("transition-script fault")
        sync_group["stop_script"] = config.return_value("transition-script stop")

        sync_groups.append(sync_group)

    # create a file with dict with proposed configuration
    with open("{}.temp".format(config_dict_path), 'w') as dict_file:
        dict_file.write(dumps({'vrrp_groups': vrrp_groups, 'sync_groups': sync_groups}))

    return (vrrp_groups, sync_groups)


def verify(data):
    vrrp_groups, sync_groups = data

    for group in vrrp_groups:
        # Check required fields
        if not group["vrid"]:
            raise ConfigError("vrid is required but not set in VRRP group {0}".format(group["name"]))
        if not group["interface"]:
            raise ConfigError("interface is required but not set in VRRP group {0}".format(group["name"]))
        if not group["virtual_addresses"]:
            raise ConfigError("virtual-address is required but not set in VRRP group {0}".format(group["name"]))

        if group["auth_password"] and (not group["auth_type"]):
            raise ConfigError("authentication type is required but not set in VRRP group {0}".format(group["name"]))

        # Keepalived doesn't allow mixing IPv4 and IPv6 in one group, so we mirror that restriction

        # XXX: filter on map object is destructive, so we force it to list.
        # Additionally, filter objects always evaluate to True, empty or not,
        # so we force them to lists as well.
        vaddrs = list(map(lambda i: ip_interface(i), group["virtual_addresses"]))
        vaddrs4 = list(filter(lambda x: isinstance(x, IPv4Interface), vaddrs))
        vaddrs6 = list(filter(lambda x: isinstance(x, IPv6Interface), vaddrs))

        if vaddrs4 and vaddrs6:
            raise ConfigError("VRRP group {0} mixes IPv4 and IPv6 virtual addresses, this is not allowed. Create separate groups for IPv4 and IPv6".format(group["name"]))

        if vaddrs4:
            if group["hello_source"]:
                hsa = ip_address(group["hello_source"])
                if isinstance(hsa, IPv6Address):
                    raise ConfigError("VRRP group {0} uses IPv4 but its hello-source-address is IPv6".format(group["name"]))
            if group["peer_address"]:
                pa = ip_address(group["peer_address"])
                if isinstance(pa, IPv6Address):
                    raise ConfigError("VRRP group {0} uses IPv4 but its peer-address is IPv6".format(group["name"]))

        if vaddrs6:
            if group["hello_source"]:
                hsa = ip_address(group["hello_source"])
                if isinstance(hsa, IPv4Address):
                    raise ConfigError("VRRP group {0} uses IPv6 but its hello-source-address is IPv4".format(group["name"]))
            if group["peer_address"]:
                pa = ip_address(group["peer_address"])
                if isinstance(pa, IPv4Address):
                    raise ConfigError("VRRP group {0} uses IPv6 but its peer-address is IPv4".format(group["name"]))

    # Disallow same VRID on multiple interfaces
    _groups = sorted(vrrp_groups, key=(lambda x: x["interface"]))
    count = len(_groups) - 1
    index = 0
    while (index < count):
        if (_groups[index]["vrid"] == _groups[index + 1]["vrid"]) and (_groups[index]["interface"] == _groups[index + 1]["interface"]):
            raise ConfigError("VRID {0} is used in groups {1} and {2} that both use interface {3}. Groups on the same interface must use different VRIDs".format(
              _groups[index]["vrid"], _groups[index]["name"], _groups[index + 1]["name"], _groups[index]["interface"]))
        else:
            index += 1

    # Check sync groups
    vrrp_group_names = list(map(lambda x: x["name"], vrrp_groups))

    for sync_group in sync_groups:
        for m in sync_group["members"]:
            if not (m in vrrp_group_names):
                raise ConfigError("VRRP sync-group {0} refers to VRRP group {1}, but group {1} does not exist".format(sync_group["name"], m))


def generate(data):
    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'vrrp')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    vrrp_groups, sync_groups = data

    # Remove disabled groups from the sync group member lists
    for sync_group in sync_groups:
        for member in sync_group["members"]:
            g = list(filter(lambda x: x["name"] == member, vrrp_groups))[0]
            if g["disable"]:
                print("Warning: ignoring disabled VRRP group {0} in sync-group {1}".format(g["name"], sync_group["name"]))
    # Filter out disabled groups
    vrrp_groups = list(filter(lambda x: x["disable"] is not True, vrrp_groups))

    tmpl = env.get_template('keepalived.conf.tmpl')
    config_text = tmpl.render({"groups": vrrp_groups, "sync_groups": sync_groups})
    with open(config_file, 'w') as f:
        f.write(config_text)

    tmpl = env.get_template('daemon.tmpl')
    config_text = tmpl.render()
    with open(daemon_file, 'w') as f:
        f.write(config_text)

    return None


def apply(data):
    vrrp_groups, sync_groups = data
    if vrrp_groups:
        # safely rename a temporary file with configuration dict
        try:
            dict_file = Path("{}.temp".format(config_dict_path))
            dict_file.rename(Path(config_dict_path))
        except Exception as err:
            print("Unable to rename the file with keepalived config for FIFO pipe: {}".format(err))

        if not vyos.keepalived.vrrp_running():
            print("Starting the VRRP process")
            ret = subprocess.call("sudo systemctl restart keepalived.service", shell=True)
        else:
            print("Reloading the VRRP process")
            ret = subprocess.call("sudo systemctl reload keepalived.service", shell=True)

        if ret != 0:
            raise ConfigError("keepalived failed to start")
    else:
        # VRRP is removed in the commit
        print("Stopping the VRRP process")
        subprocess.call("sudo systemctl stop keepalived.service", shell=True)
        os.unlink(config_file)

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print("VRRP error: {0}".format(str(e)))
        exit(1)
