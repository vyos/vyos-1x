#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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
#

import sys
import jinja2
import copy
import os
import vyos.validate

from vyos import ConfigError
from vyos.config import Config

config_file = r'/tmp/bfd.frr'

# Please be careful if you edit the template.
config_tmpl = """
!
bfd
{% for peer in old_peers -%}
 no peer {{ peer }}
{% endfor -%}
!
{% for peer in new_peers -%}
 peer {{ peer.remote }}{% if peer.multihop %} multihop{% endif %}{% if peer.local_address %} local-address {{ peer.local_address }}{% endif %}{% if peer.local_interface %} interface {{ peer.local_interface }}{% endif %}
 {% if not peer.shutdown %}no {% endif %}shutdown
{% endfor -%}
!
"""

default_config_data = {
    'new_peers': [],
    'old_peers' : []
}

def get_config():
    bfd = copy.deepcopy(default_config_data)
    conf = Config()
    if not (conf.exists('protocols bfd') or conf.exists_effective('protocols bfd')):
        return None
    else:
        conf.set_level('protocols bfd')

    # as we have to use vtysh to talk to FRR we also need to know
    # which peers are gone due to a config removal - thus we read in
    # all peers (active or to delete)
    bfd['old_peers'] = conf.list_effective_nodes('peer')

    for peer in conf.list_nodes('peer'):
        conf.set_level('protocols bfd peer {0}'.format(peer))
        bfd_peer = {
            'remote': peer,
            'shutdown': False,
            'local_interface': '',
            'local_address': '',
            'multihop': False
        }

        # Check if individual peer is disabled
        if conf.exists('shutdown'):
            bfd_peer['shutdown'] = True

        # Check if peer has a local source interface configured
        if conf.exists('local-interface'):
            bfd_peer['local_interface'] = conf.return_value('local-interface')

        # Check if peer has a local source address configured - this is mandatory for IPv6
        if conf.exists('local-address'):
            bfd_peer['local_address'] = conf.return_value('local-address')

        # Tell BFD daemon that we should expect packets with TTL less than 254
        # (because it will take more than one hop) and to listen on the multihop
        # port (4784)
        if conf.exists('multihop'):
            bfd_peer['multihop'] = True

        bfd['new_peers'].append(bfd_peer)

    return bfd

def verify(bfd):
    if bfd is None:
        return None

    for peer in bfd['new_peers']:
        # Bail out early if peer is shutdown
        if peer['shutdown']:
            continue

        # IPv6 peers require an explicit local address/interface combination
        if vyos.validate.is_ipv6(peer['remote']):
            if not (peer['local_interface'] and peer['local_address']):
                raise ConfigError("BFD IPv6 peers require explicit local address/interface setting")

    return None

def generate(bfd):
    if bfd is None:
        return None

    return None

def apply(bfd):
    if bfd is None:
        return None

    tmpl = jinja2.Template(config_tmpl)
    config_text = tmpl.render(bfd)
    with open(config_file, 'w') as f:
        f.write(config_text)

    os.system("sudo vtysh -d bfdd -f " + config_file)
    if os.path.exists(config_file):
        os.remove(config_file)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
