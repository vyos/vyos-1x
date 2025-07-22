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
from vyos.configverify import has_frr_protocol_in_dict
from vyos.configverify import verify_access_list
from vyos.configverify import verify_prefix_list
from vyos.frrender import FRRender
from vyos.frrender import get_frrender_dict
from vyos.utils.dict import dict_search
from vyos.utils.process import is_systemd_service_running
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
    if not has_frr_protocol_in_dict(config_dict, 'babel'):
        return None

    babel = config_dict['babel']
    babel['policy'] = config_dict['policy']

    # verify distribute_list
    if "distribute_list" in babel:
        acl_keys = {
            "ipv4": [
                "distribute_list.ipv4.access_list.in",
                "distribute_list.ipv4.access_list.out",
            ],
            "ipv6": [
                "distribute_list.ipv6.access_list.in",
                "distribute_list.ipv6.access_list.out",
            ]
        }
        prefix_list_keys = {
            "ipv4": [
                "distribute_list.ipv4.prefix_list.in",
                "distribute_list.ipv4.prefix_list.out",
            ],
            "ipv6":[
                "distribute_list.ipv6.prefix_list.in",
                "distribute_list.ipv6.prefix_list.out",
            ]
        }
        for address_family in ["ipv4", "ipv6"]:
            for iface_key in babel["distribute_list"].get(address_family, {}).get("interface", {}).keys():
                acl_keys[address_family].extend([
                    f"distribute_list.{address_family}.interface.{iface_key}.access_list.in",
                    f"distribute_list.{address_family}.interface.{iface_key}.access_list.out"
                ])
                prefix_list_keys[address_family].extend([
                    f"distribute_list.{address_family}.interface.{iface_key}.prefix_list.in",
                    f"distribute_list.{address_family}.interface.{iface_key}.prefix_list.out"
                ])

        for address_family, keys in acl_keys.items():
            for key in keys:
                acl = dict_search(key, babel)
                if acl:
                    verify_access_list(acl, babel, version='6' if address_family == 'ipv6' else '')

        for address_family, keys in prefix_list_keys.items():
            for key in keys:
                prefix_list = dict_search(key, babel)
                if prefix_list:
                    verify_prefix_list(prefix_list, babel, version='6' if address_family == 'ipv6' else '')


def generate(config_dict):
    if config_dict and not is_systemd_service_running('vyos-configd.service'):
        FRRender().generate(config_dict)
    return None

def apply(config_dict):
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
