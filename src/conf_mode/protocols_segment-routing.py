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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sys import exit

from vyos.config import Config
from vyos.configdict import node_changed
from vyos.template import render_to_string
from vyos.utils.dict import dict_search
from vyos.utils.system import sysctl_write
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['protocols', 'segment-routing']
    sr = conf.get_config_dict(base, key_mangling=('-', '_'),
                              get_first_key=True,
                              no_tag_node_value_mangle=True,
                              with_recursive_defaults=True)

    # FRR has VRF support for different routing daemons. As interfaces belong
    # to VRFs - or the global VRF, we need to check for changed interfaces so
    # that they will be properly rendered for the FRR config. Also this eases
    # removal of interfaces from the running configuration.
    interfaces_removed = node_changed(conf, base + ['interface'])
    if interfaces_removed:
        sr['interface_removed'] = list(interfaces_removed)

    import pprint
    pprint.pprint(sr)
    return sr

def verify(sr):
    if 'srv6' in sr:
        srv6_enable = False
        if 'interface' in sr:
            for interface, interface_config in sr['interface'].items():
                if 'srv6' in interface_config:
                    srv6_enable = True
                    break
        if not srv6_enable:
            raise ConfigError('SRv6 should be enabled on at least one interface!')
    return None

def generate(sr):
    if not sr:
        return None

    sr['new_frr_config'] = render_to_string('frr/zebra.segment_routing.frr.j2', sr)
    return None

def apply(sr):
    zebra_daemon = 'zebra'

    if 'interface_removed' in sr:
        for interface in sr['interface_removed']:
            # Disable processing of IPv6-SR packets
            sysctl_write(f'net.ipv6.conf.{interface}.seg6_enabled', '0')

    if 'interface' in sr:
        for interface, interface_config in sr['interface'].items():
            # Accept or drop SR-enabled IPv6 packets on this interface
            if 'srv6' in interface_config:
                sysctl_write(f'net.ipv6.conf.{interface}.seg6_enabled', '1')
                # Define HMAC policy for ingress SR-enabled packets on this interface
                # It's a redundant check as HMAC has a default value - but better safe
                # then sorry
                tmp = dict_search('srv6.hmac', interface_config)
                if tmp == 'accept':
                    sysctl_write(f'net.ipv6.conf.{interface}.seg6_require_hmac', '0')
                elif tmp == 'drop':
                    sysctl_write(f'net.ipv6.conf.{interface}.seg6_require_hmac', '1')
                elif tmp == 'ignore':
                    sysctl_write(f'net.ipv6.conf.{interface}.seg6_require_hmac', '-1')
            else:
                sysctl_write(f'net.ipv6.conf.{interface}.seg6_enabled', '0')

    # Save original configuration prior to starting any commit actions
    frr_cfg = frr.FRRConfig()
    frr_cfg.load_configuration(zebra_daemon)
    frr_cfg.modify_section(r'^segment-routing')
    if 'new_frr_config' in sr:
        frr_cfg.add_before(frr.default_add_before, sr['new_frr_config'])
    frr_cfg.commit_configuration(zebra_daemon)

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
