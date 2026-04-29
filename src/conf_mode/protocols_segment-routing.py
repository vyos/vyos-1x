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
from sys import argv

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

    return get_frrender_dict(conf, argv)

def verify(config_dict):
    if not has_frr_protocol_in_dict(config_dict, 'segment_routing'):
        return None

    sr = config_dict['segment_routing']

    if 'srv6' in sr:
        srv6_enable = False
        for _, interface_config in dict_search('interface', sr, {}).items():
            if 'srv6' in interface_config:
                srv6_enable = True
                break
        if not srv6_enable:
            raise ConfigError('SRv6 should be enabled on at least one interface!')

    # Check for database import having more than one protocol
    if tmp := dict_search('traffic_engineering.database_import_protocol', sr):
        if {'isis', 'ospf'} <= set(tmp.keys()):
            raise ConfigError('SR-TE database import: IS-IS and OSPF are mutually exclusive!')

    for segment_list in dict_search('traffic_engineering.segment_list', sr, []):
        sl_data = dict_search(f'traffic_engineering.segment_list.{segment_list}', sr)
        indices = sl_data.get('index') if sl_data else None

        if indices is None:
            raise ConfigError(f'SR-TE segment list "{segment_list}": '\
                               'at least one index is required!')

        for index, index_data in indices.items():
            error_msg = f'SR-TE segment list "{segment_list}", index "{index}"'
            nai = index_data.get('nai')
            mpls = index_data.get('mpls')
            if not nai and not mpls:
                raise ConfigError(f'{error_msg}: "mpls" or "nai" is required!')

            if nai:
                if 'adjacency' in nai and 'prefix' in nai:
                    raise ConfigError(f'{error_msg}: "prefix" and "adjacency" are mutually exclusive!')

                for nai_type in ('adjacency', 'prefix'):
                    nai_data = nai.get(nai_type)
                    if not nai_data:
                        continue

                    if 'ipv4' in nai_data and 'ipv6' in nai_data:
                        raise ConfigError(f'{error_msg}, nai {nai_type}: "ipv4" and "ipv6" are '
                                           'mutually exclusive!')

                    for af, af_config in nai_data.items():
                        af_ctx = f'{error_msg}, nai {nai_type} {af}'
                        if nai_type == 'adjacency':
                            has_src = 'source_identifier' in af_config
                            has_dst = 'destination_identifier' in af_config
                            if has_src != has_dst:
                                missing = 'destination-identifier' if has_src else 'source-identifier'
                                raise ConfigError(f'{af_ctx}: "{missing}" is required!')
                        else:
                            if 'prefix_identifier' not in af_config:
                                raise ConfigError(f'{af_ctx}: "prefix-identifier" is required!')

                            for pfx, pfx_data in af_config['prefix_identifier'].items():
                                pfx_ctx = f'{af_ctx}, prefix "{pfx}"'
                                if 'algorithm' not in pfx_data:
                                    raise ConfigError(f'{pfx_ctx}: "algorithm" is required!')

                                if alg := pfx_data.get('algorithm'):
                                    if {'spf', 'strict_spf'} <= set(alg.keys()):
                                        raise ConfigError(f'{pfx_ctx}: "spf" and "strict-spf" '
                                                           'are mutually exclusive!')

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
        sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_enabled'], '0')

    for interface, interface_config in sr.get('interface', {}).items():
        # Accept or drop SR-enabled IPv6 packets on this interface
        if 'srv6' in interface_config:
            sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_enabled'], '1')
            # Define HMAC policy for ingress SR-enabled packets on this interface
            # It's a redundant check as HMAC has a default value - but better safe
            # then sorry
            tmp = dict_search('srv6.hmac', interface_config)
            if tmp == 'accept':
                sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac'], '0')
            elif tmp == 'drop':
                sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac'], '1')
            elif tmp == 'ignore':
                sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_require_hmac'], '-1')
        else:
            sysctl_write(['net', 'ipv6', 'conf', interface, 'seg6_enabled'], '0')

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
