# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

from vyos.configdict import list_diff
from vyos.ifconfig import Interface
from vyos.utils.assertion import assert_list
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.utils.network import get_vxlan_vlan_tunnels
from vyos.utils.network import get_vxlan_vni_filter

@Interface.register
class VXLANIf(Interface):
    """
    The VXLAN protocol is a tunnelling protocol designed to solve the
    problem of limited VLAN IDs (4096) in IEEE 802.1q. With VXLAN the
    size of the identifier is expanded to 24 bits (16777216).

    VXLAN is described by IETF RFC 7348, and has been implemented by a
    number of vendors.  The protocol runs over UDP using a single
    destination port.  This document describes the Linux kernel tunnel
    device, there is also a separate implementation of VXLAN for
    Openvswitch.

    Unlike most tunnels, a VXLAN is a 1 to N network, not just point to
    point. A VXLAN device can learn the IP address of the other endpoint
    either dynamically in a manner similar to a learning bridge, or make
    use of statically-configured forwarding entries.

    For more information please refer to:
    https://www.kernel.org/doc/Documentation/networking/vxlan.txt
    """

    iftype = 'vxlan'
    definition = {
        **Interface.definition,
        **{
            'section': 'vxlan',
            'prefixes': ['vxlan', ],
            'bridgeable': True,
        }
    }

    _command_set = {**Interface._command_set, **{
        'neigh_suppress': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': 'bridge link set dev {ifname} neigh_suppress {value} learning off',
        },
        'vlan_tunnel': {
            'validate': lambda v: assert_list(v, ['on', 'off']),
            'shellcmd': 'bridge link set dev {ifname} vlan_tunnel {value}',
        },
    }}

    def _create(self):
        # This table represents a mapping from VyOS internal config dict to
        # arguments used by iproute2. For more information please refer to:
        # - https://man7.org/linux/man-pages/man8/ip-link.8.html
        mapping = {
            'group'                      : 'group',
            'gpe'                        : 'gpe',
            'parameters.external'        : 'external',
            'parameters.ip.df'           : 'df',
            'parameters.ip.tos'          : 'tos',
            'parameters.ip.ttl'          : 'ttl',
            'parameters.ipv6.flowlabel'  : 'flowlabel',
            'parameters.nolearning'      : 'nolearning',
            'parameters.vni_filter'      : 'vnifilter',
            'remote'                     : 'remote',
            'source_address'             : 'local',
            'source_interface'           : 'dev',
            'vni'                        : 'id',
        }

        # IPv6 flowlabels can only be used on IPv6 tunnels, thus we need to
        # ensure that at least the first remote IP address is passed to the
        # tunnel creation command. Subsequent tunnel remote addresses can later
        # be added to the FDB
        remote_list = None
        if 'remote' in self.config:
            # skip first element as this is already configured as remote
            remote_list = self.config['remote'][1:]
            self.config['remote'] = self.config['remote'][0]

        cmd = 'ip link add {ifname} type {type} dstport {port}'
        for vyos_key, iproute2_key in mapping.items():
            # dict_search will return an empty dict "{}" for valueless nodes like
            # "parameters.nolearning" - thus we need to test the nodes existence
            # by using isinstance()
            tmp = dict_search(vyos_key, self.config)
            if isinstance(tmp, dict):
                cmd += f' {iproute2_key}'
            elif tmp != None:
                cmd += f' {iproute2_key} {tmp}'

        self._cmd(cmd.format(**self.config))
        # interface is always A/D down. It needs to be enabled explicitly
        self.set_admin_state('down')

        # VXLAN tunnel is always recreated on any change - see interfaces_vxlan.py
        if remote_list:
            for remote in remote_list:
                cmd = f'bridge fdb append to 00:00:00:00:00:00 dst {remote} ' \
                       'port {port} dev {ifname}'
                self._cmd(cmd.format(**self.config))

    def set_neigh_suppress(self, state):
        """
        Controls whether neigh discovery (arp and nd) proxy and suppression
        is enabled on the port. By default this flag is off.
        """

        # Determine current OS Kernel neigh_suppress setting - only adjust when needed
        tmp = get_interface_config(self.ifname)
        cur_state = 'on' if dict_search(f'linkinfo.info_slave_data.neigh_suppress', tmp) == True else 'off'
        new_state = 'on' if state else 'off'
        if cur_state != new_state:
            self.set_interface('neigh_suppress', state)

    def set_vlan_vni_mapping(self, state):
        """
        Controls whether vlan to tunnel mapping is enabled on the port.
        By default this flag is off.
        """
        if not isinstance(state, bool):
            raise ValueError('Value out of range')

        if 'vlan_to_vni_removed' in self.config:
            cur_vni_filter = None
            if dict_search('parameters.vni_filter', self.config) != None:
                cur_vni_filter = get_vxlan_vni_filter(self.ifname)

            for vlan, vlan_config in self.config['vlan_to_vni_removed'].items():
                # If VNI filtering is enabled, remove matching VNI filter
                if cur_vni_filter != None:
                    vni = vlan_config['vni']
                    if vni in cur_vni_filter:
                        self._cmd(f'bridge vni delete dev {self.ifname} vni {vni}')
                self._cmd(f'bridge vlan del dev {self.ifname} vid {vlan}')

        # Determine current OS Kernel vlan_tunnel setting - only adjust when needed
        tmp = get_interface_config(self.ifname)
        cur_state = 'on' if dict_search(f'linkinfo.info_slave_data.vlan_tunnel', tmp) == True else 'off'
        new_state = 'on' if state else 'off'
        if cur_state != new_state:
            self.set_interface('vlan_tunnel', new_state)

        if 'vlan_to_vni' in self.config:
            # Determine current OS Kernel configured VLANs
            os_configured_vlan_ids = get_vxlan_vlan_tunnels(self.ifname)
            add_vlan = list_diff(list(self.config['vlan_to_vni'].keys()), os_configured_vlan_ids)

            for vlan, vlan_config in self.config['vlan_to_vni'].items():
                # VLAN mapping already exists - skip
                if vlan not in add_vlan:
                    continue

                vni = vlan_config['vni']
                # The following commands must be run one after another,
                # they can not be combined with linux 6.1 and iproute2 6.1
                self._cmd(f'bridge vlan add dev {self.ifname} vid {vlan}')
                self._cmd(f'bridge vlan add dev {self.ifname} vid {vlan} tunnel_info id {vni}')

                # If VNI filtering is enabled, install matching VNI filter
                if dict_search('parameters.vni_filter', self.config) != None:
                    self._cmd(f'bridge vni add dev {self.ifname} vni {vni}')

    def update(self, config):
        """ General helper function which works on a dictionary retrived by
        get_config_dict(). It's main intention is to consolidate the scattered
        interface setup code and provide a single point of entry when workin
        on any interface. """

        # call base class last
        super().update(config)

        # Enable/Disable VLAN tunnel mapping
        # This is only possible after the interface was assigned to the bridge
        self.set_vlan_vni_mapping(dict_search('vlan_to_vni', config) != None)

        # Enable/Disable neighbor suppression and learning, there is no need to
        # explicitly "disable" it, as VXLAN interface will be recreated if anything
        # under "parameters" changes.
        if dict_search('parameters.neighbor_suppress', config) != None:
            self.set_neigh_suppress('on')
