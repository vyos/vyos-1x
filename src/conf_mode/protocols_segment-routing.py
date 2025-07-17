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

from sys import exit

from vyos.config import Config
from vyos.configdict import list_diff
from vyos.configverify import has_frr_protocol_in_dict
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.ifconfig import Section
from vyos.utils.dict import dict_search
from vyos.utils.process import is_systemd_service_running
from vyos.utils.system import sysctl_write
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
    if not has_frr_protocol_in_dict(config_dict, 'segment_routing'):
        return None

    sr = config_dict['segment_routing']

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

def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'segment_routing'):
        return None

    sr = config_dict['segment_routing']

    current_interfaces = Section.interfaces()
    sr_interfaces = list(sr.get('interface', {}).keys())

    for interface in list_diff(current_interfaces, sr_interfaces):
        # Disable processing of IPv6-SR packets
        sysctl_write(f'net.ipv6.conf.{interface}.seg6_enabled', '0')

    for interface, interface_config in sr.get('interface', {}).items():
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

    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().apply()
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
