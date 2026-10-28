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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import re

from sys import exit

from glob import glob
from vyos.config import Config
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.utils.file import read_file
from vyos.utils.process import is_systemd_service_active
from vyos.utils.system import sysctl_write
from vyos.configverify import verify_interface_exists
from vyos.vpp.control_vpp import VPPControl
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    return get_frrender_dict(conf)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'mpls'):
        return None

    mpls = config_dict['mpls']

    if 'interface' in mpls:
        for interface in mpls['interface']:
            verify_interface_exists(mpls, interface)
            # The entry of a VPP interface (vppbond0, vpplo1, ...) does not
            # survive the load of the saved configuration at boot: the name
            # does not match the interface name constraint and the interface
            # does not exist yet.
            if re.match(r'vpp(?!tap|tun)', interface):
                raise ConfigError(
                    f'MPLS is not supported on the VPP interface "{interface}", '
                    f'only on physical interfaces and their VLANs!'
                )

    # Checks to see if LDP is properly configured
    if 'ldp' in mpls:
        # If router ID not defined
        if 'router_id' not in mpls['ldp']:
            raise ConfigError('Router ID missing. An LDP router id is mandatory!')

        # If interface not set
        if 'interface' not in mpls['ldp']:
            raise ConfigError('LDP interfaces are missing. An LDP interface is mandatory!')

        # If transport addresses are not set
        if not dict_search('ldp.discovery.transport_ipv4_address', mpls) and \
           not dict_search('ldp.discovery.transport_ipv6_address', mpls):
                raise ConfigError('LDP transport address missing!')

    return None

def generate(config_dict):
    return None

def apply(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'mpls'):
        return None

    mpls = config_dict['mpls']

    # Set number of entries in the platform label tables
    labels = '0'
    if 'interface' in mpls:
        labels = '1048575'
    sysctl_write(['net', 'mpls', 'platform_labels'], labels)

    # Check for changes in global MPLS options
    if 'parameters' in mpls:
            # Choose whether to copy IP TTL to MPLS header TTL
        if 'no_propagate_ttl' in mpls['parameters']:
            sysctl_write(['net', 'mpls', 'ip_ttl_propagate'], 0)
            # Choose whether to limit maximum MPLS header TTL
        if 'maximum_ttl' in mpls['parameters']:
            ttl = mpls['parameters']['maximum_ttl']
            sysctl_write(['net', 'mpls', 'default_ttl'], ttl)
    else:
        # Set default global MPLS options if not defined.
        sysctl_write(['net', 'mpls', 'ip_ttl_propagate'], 1)
        sysctl_write(['net', 'mpls', 'default_ttl'], 255)

    # Enable and disable MPLS processing on interfaces per configuration
    if 'interface' in mpls:
        system_interfaces = []
        # Populate system interfaces list with local MPLS capable interfaces
        for interface in glob('/proc/sys/net/mpls/conf/*'):
            system_interfaces.append(os.path.basename(interface))
        # This is where the comparison is done on if an interface needs to be enabled/disabled.
        for system_interface in system_interfaces:
            interface_state = read_file(f'/proc/sys/net/mpls/conf/{system_interface}/input')
            if '1' in interface_state:
                if system_interface not in mpls['interface']:
                    sysctl_write(['net', 'mpls', 'conf', system_interface, 'input'], 0)
            elif '0' in interface_state:
                if system_interface in mpls['interface']:
                    sysctl_write(['net', 'mpls', 'conf', system_interface, 'input'], 1)
    else:
        system_interfaces = []
        # If MPLS interfaces are not configured, set MPLS processing disabled
        for interface in glob('/proc/sys/net/mpls/conf/*'):
            system_interfaces.append(os.path.basename(interface))
        for system_interface in system_interfaces:
            sysctl_write(['net', 'mpls', 'conf', system_interface, 'input'], 0)

    # VPP drops labeled packets on an interface that has MPLS disabled,
    # whatever the kernel setting is. linux-cp copies the state to the kernel
    # interface of the pair, also when the pair is created later, as it is for
    # a VLAN sub-interface after a rebuild. So enable it by the VPP name, found
    # through the pair of the interface or of its parent.
    if is_systemd_service_active('vpp.service'):
        vpp = VPPControl()
        enabled = vpp.mpls_enabled_interfaces()
        pairs = {pair['kernel_name']: pair for pair in vpp.lcp_pairs_list()}

        def vpp_name(name):
            if name in pairs:
                return pairs[name]['vpp_name_hw']
            parent, _, vlan_id = name.rpartition('.')
            parent_name = vpp_name(parent) if parent and vlan_id.isdigit() else None
            return f'{parent_name}.{vlan_id}' if parent_name else None

        wanted = []
        for name in mpls.get('interface', {}):
            vpp_ifname = vpp_name(name)
            index = vpp.get_sw_if_index(vpp_ifname) if vpp_ifname else None
            if index is None:
                continue
            wanted.append(index)
            if index not in enabled:
                vpp.set_interface_mpls(vpp_ifname, True)
        for pair in pairs.values():
            if pair['vpp_index_hw'] in enabled and pair['vpp_index_hw'] not in wanted:
                vpp.set_interface_mpls(pair['vpp_name_hw'], False)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
