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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
# This script will generate ZeroTier interfaces from containers, as well
# as generate the local.conf file for advanced ZeroTier configurations.

import datetime
import json
import os
import re
import shutil
import sys
import textwrap

from collections import Counter

from vyos.utils.process import cmd, rc_cmd
from vyos.config import Config
from vyos import ConfigError

def generate_local_conf(data):
    # Base local.conf
    local_conf_dict = {
            "physical": {},
            "virtual": {},
            "settings": {}
        }

    ############################################################
    #################### Physical Dict Path ####################
    ############################################################
    if data.get('network_config'):
        for network in data.get('network_config').keys():
            local_conf_dict['physical'][network] = {}
            mtu = data.get('network_config').get(network).get('mtu')

            if mtu:
                local_conf_dict['physical'][network]['mtu'] = int(mtu)

            if data.get('mtu'):
                local_conf_dict['physical'][network]['mtu'] = data.get('network_config').get("mtu")

            if isinstance(data.get('network_config').get(network).get('blacklist'), dict):
                local_conf_dict['physical'][network]['blacklist'] = True

    ############################################################
    #################### Virtual Dict Path #####################
    ############################################################
    if data.get('peer_config'):
        for peer in data.get('peer_config').keys():
            local_conf_dict['virtual'][peer] = {}

            if data.get('peer_config').get(peer).get('blacklist'):
                local_conf_dict['virtual'][peer]['blacklist'] = data.get('peer_config').get(peer).get('blacklist')
            if data.get('peer_config').get(peer).get('try'):
                local_conf_dict['virtual'][peer]['try'] = data.get('peer_config').get(peer).get('try')

    ############################################################
    #################### Settings Dict Path ####################
    ############################################################
    if isinstance(data.get('low_bandwidth_mode'), dict):
        local_conf_dict['settings']['lowBandwidthMode'] = True
    if isinstance(data.get('allow_tcp_fallback'), dict):
        local_conf_dict['settings']['allowTcpFallbackRelay'] = True
    if isinstance(data.get('force_tcp_relay'), dict):
        local_conf_dict['settings']['forceTcpRelay'] = True
    if data.get('primary_port'):
        local_conf_dict['settings']['primaryPort'] = int(data.get("primary_port", 9993))
    if data.get('secondary_port'):
        local_conf_dict['settings']['secondaryPort'] = int(data.get("secondary_port"))
    if data.get('tertiary_port'):
        local_conf_dict['settings']['tertiaryPort'] = int(data.get("tertiary_port"))
    if data.get('bind'):
        local_conf_dict['settings']['bind'] = data.get("bind")
    if data.get('allow_mgmt_from'):
        local_conf_dict['settings']['allowManagementFrom'] = data.get("allow_mgmt_from")
    if data.get('interface_blacklist'):
        local_conf_dict['settings']['interfacePrefixBlacklist'] = data.get("interface_blacklist")
    if data.get('multipath_mode'):
        local_conf_dict['settings']['multipathMode'] = int(data.get("multipath_mode"))
    if data.get('tcp_relay'):
        local_conf_dict['settings']['tcpFallbackRelay'] = data.get("tcp_relay")

    ############################################################
    #################### Multipath Dict Path ###################
    ############################################################
    if data.get('custom_policy'):
        local_conf_dict['settings']['policies'] = {}
        for policy in data.get('custom_policy').keys():
            local_conf_dict['settings']['policies'][policy] = {}

            if data.get('custom_policy').get(policy).get('link_select_method'):
                local_conf_dict['settings']['policies'][policy]['linkSelectMethod'] = data.get('custom_policy').get(policy).get("link_select_method")

            if data.get('custom_policy').get(policy).get('down_delay'):
                local_conf_dict['settings']['policies'][policy]['downDelay'] = int(data.get('custom_policy').get(policy).get("down_delay"))

            if data.get('custom_policy').get(policy).get('up_delay'):
                local_conf_dict['settings']['policies'][policy]['upDelay'] = int(data.get('custom_policy').get(policy).get("up_delay"))

            if data.get('custom_policy').get(policy).get('failover_interval'):
                local_conf_dict['settings']['policies'][policy]['failoverInterval'] = int(data.get('custom_policy').get(policy).get("failover_interval"))

            if data.get('custom_policy').get(policy).get('base_policy'):
                local_conf_dict['settings']['policies'][policy]['basePolicy'] = data.get('custom_policy').get(policy).get("base_policy")

            if data.get('custom_policy').get(policy).get('link_quality'):
                local_conf_dict['settings']['policies'][policy]['linkQuality'] = {}

                if data.get('custom_policy').get(policy).get('link_quality').get('max_latency'):
                    local_conf_dict['settings']['policies'][policy]['linkQuality']['lat_max'] = float(data.get('custom_policy').get(policy).get('link_quality').get('max_latency'))

                if data.get('custom_policy').get(policy).get('link_quality').get('max_variance'):
                    local_conf_dict['settings']['policies'][policy]['linkQuality']['pdv_max'] = float(data.get('custom_policy').get(policy).get('link_quality').get('max_variance'))

                if data.get('custom_policy').get(policy).get('link_quality').get('latency_weight'):
                    local_conf_dict['settings']['policies'][policy]['linkQuality']['lat_weight'] = float(data.get('custom_policy').get(policy).get('link_quality').get('latency_weight'))/10

                if data.get('custom_policy').get(policy).get('link_quality').get('variance_weight'):
                    local_conf_dict['settings']['policies'][policy]['linkQuality']['pdv_weight'] = float(data.get('custom_policy').get(policy).get('link_quality').get('variance_weight'))/10

            if data.get('custom_policy').get(policy).get('links'):
                local_conf_dict['settings']['policies'][policy]['links'] = {}
                for link in data.get('custom_policy').get(policy).get('links'):
                    local_conf_dict['settings']['policies'][policy]['links'][link] = {}

                    if data.get('custom_policy').get(policy).get('links').get(link).get('mode'):
                        local_conf_dict['settings']['policies'][policy]['links'][link]['mode'] = data.get('custom_policy').get(policy).get('links').get(link).get("mode")

                    if data.get('custom_policy').get(policy).get('links').get(link).get('ip_pref'):
                        local_conf_dict['settings']['policies'][policy]['links'][link]['ip_pref'] = int(data.get('custom_policy').get(policy).get('links').get(link).get("ip_pref"))

                    if data.get('custom_policy').get(policy).get('links').get(link).get('failover_to'):
                        local_conf_dict['settings']['policies'][policy]['links'][link]['failover_to'] = data.get('custom_policy').get(policy).get('links').get(link).get("failover_to")

                    if data.get('custom_policy').get(policy).get('links').get(link).get('capacity'):
                        local_conf_dict['settings']['policies'][policy]['links'][link]['capacity'] = int(data.get('custom_policy').get(policy).get('links').get(link).get("capacity"))

    if data.get('peer_specific_bonds'):
        local_conf_dict['settings']['peerSpecificBonds'] = {}
        for peer in data.get('peer_specific_bonds').keys():
            local_conf_dict['settings']['peerSpecificBonds'][peer] = {}
            local_conf_dict['settings']['peerSpecificBonds'][peer] = data.get("peer_specific_bonds").get(peer).get('bond_name')

    if data.get('bonding_policy'):
        local_conf_dict['settings']['defaultBondingPolicy'] = data.get("bonding_policy")

    return local_conf_dict

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['interfaces','zerotier']

    config_data = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     no_tag_node_value_mangle=True,
                                     get_first_key=True,
                                     with_recursive_defaults=True)

    return config_data

def verify(config):
    primaryPortList = []

    for i in config:
        verify_data = config[i]
        priPort = config.get(i).get("primary_port")

        if not config.get(i).get('version'):
            raise ConfigError("Version must be configured")
        image_name = f"zerotier/zerotier:{config.get(i).get('version')}"

        # Primary Port must be configured
        if not priPort:
            raise ConfigError("Primary Port must be configured")

        # Network ID must be configured
        if not config.get(i).get('network_id'):
            raise ConfigError("Network ID must be configured")

        # Check if container images is present
        if not cmd(f"sudo podman images -q {image_name}"):
            print(re.sub(r'(?<!\n)\n(?!\n)', ' ', textwrap.dedent(f"""\
                {image_name} container not present. Ensure that you follow all necessary licensing requirements
                for using ZeroTier.

                Image installation can be performed using the following op command (Requires Internet Access):
                                  """)) + "\n")
            raise ConfigError(f"add container image {image_name}")

        # latency weight and delay variance weight must equal 10
        if verify_data.get('custom_policy'):
            for policy in verify_data.get('custom_policy').keys():
                if verify_data.get('custom_policy').get(policy).get('link_quality'):
                    lat_weight = float(verify_data.get('custom_policy').get(policy).get('link_quality').get('latency_weight'))/10
                    pdv_weight = float(verify_data.get('custom_policy').get(policy).get('link_quality').get('variance_weight'))/10

                    if lat_weight or pdv_weight:
                        if lat_weight and pdv_weight:
                            if lat_weight+pdv_weight != 1:
                                raise ConfigError("latency-weight and variance-weight must equal 10")
                        else:
                            raise ConfigError("latency-weight and variance-weight must be configured together")

        primaryPortList.append(priPort)

    # Unique ports must be used per interface
    dupCheck = [item for item, count in Counter(primaryPortList).items() if count > 1]
    if dupCheck:
        raise ConfigError(f"Primary Port {', '.join(dupCheck)} configured on more than one interface")

def generate(config):
    global podmanDict
    podmanDict = {}

    # Build Quadlet configuration
    for i in config:
        podman_quadlet = textwrap.dedent(f"""
            [Unit]
            Description=Podman container vyos_created_{i}
            Wants=network-online.target
            After=network-online.target

            [Service]
            Type=simple
            User=root
            Group=root
            ExecStartPre=-/usr/bin/podman rm -f vyos_created_{i}
            ExecStart=/usr/bin/podman run --name vyos_created_{i} \\
                --device=/dev/net/tun \\
                --net=host \\
                --cap-add=NET_ADMIN \\
                --cap-add=SYS_ADMIN \\
                --restart=always \\
                --no-healthcheck \\
                -v /config/vyos-zerotier/{i}:/var/lib/zerotier-one \\
                zerotier/zerotier:{config.get(i).get('version')}
            ExecStop=/usr/bin/podman stop vyos_created_{i}
            ExecReload=/usr/bin/podman restart vyos_created_{i}
            Restart=always
            RestartSec=5s

            [Install]
            WantedBy=multi-user.target
            """)

        # Generate the local.conf file for ZeroTier
        local_conf = json.dumps(generate_local_conf(config[i]))

        # Generate the configuration dict to use with apply()
        podmanDict[i] = {
        "local_conf_content": local_conf,
        "network_id": config.get(i).get("network_id"),
        "api_key": config.get(i).get("api_key"),
        "mtu": config.get(i).get("mtu"),
        "image_name": f"zerotier/zerotier:{config.get(i).get('version')}",
        "podman_quadlet": podman_quadlet
        }

    return podmanDict

def apply(config):
    path = f"/config/vyos-zerotier/"

    # Check if the directory exists
    if not os.path.exists(path):
        os.makedirs(path)

    # Get list of ZeroTier interface config directories
    directories = [d for d in os.listdir(path) if os.path.isdir(os.path.join(path, d))]

    for i in podmanDict:
        local_conf_changed, network_id_changed, version_changed = False, False, False
        networkID = podmanDict.get(i).get('network_id')
        image_name = podmanDict.get(i).get('image_name')
        container_data = json.loads(cmd(f"podman container list --format json"))
        os.makedirs(f"/config/vyos-zerotier/{i}/networks.d", exist_ok=True)

        # Check if version has changed
        for con in container_data:
            if i in con.get('Names')[0]:
                if image_name not in con.get('Image'):
                    version_changed = True

        # Check if new local.conf is different from existing local.conf
        try:
            with open(f"/config/vyos-zerotier/{i}/local.conf", "r") as file:
                if json.load(file) != json.loads(podmanDict[i]['local_conf_content']):
                    local_conf_changed = True
        except:
            local_conf_changed = True

        # Write new local.conf to
        if local_conf_changed:
            with open(f"/config/vyos-zerotier/{i}/local.conf", "w") as file:
                file.write(podmanDict[i]['local_conf_content'])

        if networkID:
            # Create <net-id>.local.conf; used to deterime if network should be joined
            with open(f"/config/vyos-zerotier/{i}/networks.d/{networkID}.conf", "w") as file:
                file.write("")

            # Create devicemap; used to map zerotier interface to named interface
            with open(f"/config/vyos-zerotier/{i}/devicemap", "w") as file:
                file.write(f"{networkID}={i}")

        # Check if network-id has changed; if changed delete old <net-id>.local.conf
        for filename in os.listdir(f"/config/vyos-zerotier/{i}/networks.d"):
            file_path = os.path.join(f"/config/vyos-zerotier/{i}/networks.d", filename)
            if os.path.isfile(file_path):
                if networkID:
                    if filename.replace(".conf", "") not in networkID:
                        os.remove(file_path)
                        network_id_changed = True
                else:
                    os.remove(file_path)

        # Write service Quadlet for container to disk
        with open(f"/etc/systemd/system/vyos-zerotier@{i}.service", 'w') as file:
            file.write(podmanDict.get(i).get('podman_quadlet'))

        # Create services for ZeroTier containers
        cmd("sudo systemctl daemon-reload")

        enabled = rc_cmd(f"sudo systemctl is-enabled vyos-zerotier@{i}.service")[1].strip()

        # If services is not enabled, enable and start it
        if enabled != "enabled":
            cmd(f"sudo systemctl enable --now vyos-zerotier@{i}.service")
            cmd(f"sudo systemctl start vyos-zerotier@{i}.service")
        else:
            if local_conf_changed or network_id_changed or version_changed:
                cmd(f"sudo systemctl restart vyos-zerotier@{i}.service")

    containers = json.loads(cmd("podman ps --format json"))

    # Stop and remove container if interface is deleted
    for container in containers:
        if f"{container['Names'][0]}".replace("vyos_created_", "") not in podmanDict.keys():
            cmd(f"podman container stop {container.get('Names')[0]}")
            cmd(f"podman container rm {container.get('Names')[0]}")

    # Since elements in the config directory are important to node identities and secrets,
    # backup config directory so it can be restored if deleted on accident
    for i in directories:
        if i not in podmanDict.keys() and i != "backup":
            timestamp = datetime.datetime.now().strftime("%m-%d-%H%M")

            # Backup the directory for key recovery if necessary
            shutil.make_archive(f"/config/vyos-zerotier/backup/{i}_{timestamp}.bak", 'zip', i,f"{path}{i}")

            # Remove the directory for the deleted interface
            shutil.rmtree(f"{path}{i}")

            # Delete to service for the deleted interface
            cmd(f"sudo systemctl stop vyos-zerotier@{i}.service")
            cmd(f"sudo systemctl disable vyos-zerotier@{i}.service")
            os.remove(f"/etc/systemd/system/vyos-zerotier@{i}.service")
            cmd(f"sudo systemctl daemon-reload")

try:
    c = get_config()
    verify(c)
    generate(c)
    apply(c)
except ConfigError as e:
    print(e)
    sys.exit(1)
