#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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
from vyos.util import call
from vyos.util import dict_search
from vyos.template import render
from vyos.template import render_to_string
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

config_file = r'/tmp/bgp.frr'

def get_config():
    conf = Config()
    base = ['protocols', 'nbgp']
    bgp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)

    # XXX: any reason we can not move this into the FRR template?
    # we shall not call vtysh directly, especially not in get_config()
    if not conf.exists(base):
        bgp = {}
        call('vtysh -c \"conf t\" -c \"no ip protocol bgp\" ')

    if not conf.exists(base + ['route-map']):
        call('vtysh -c \"conf t\" -c \"no ip protocol bgp\" ')

    return bgp

def verify(bgp):
    if not bgp:
        return None

    # Check if declared more than one ASN
    if len(bgp) > 1:
        raise ConfigError('Only one BGP AS can be defined!')

    for asn, asn_config in bgp.items():
        # Common verification for both peer-group and neighbor statements
        for neigh in ['neighbor', 'peer_group']:
            # bail out early if there is no neighbor or peer-group statement
            # this also saves one indention level
            if neigh not in asn_config:
                continue

            for neighbor, config in asn_config[neigh].items():
                if 'remote_as' not in config and 'peer_group' not in config:
                    raise ConfigError(f'BGP remote-as must be specified for "{neighbor}"!')

                if 'remote_as' in config and 'peer_group' in config:
                    raise ConfigError(f'BGP peer-group member "{neighbor}" cannot override remote-as of peer-group!')

    return None

def generate(bgp):
    if not bgp:
        bgp['new_frr_config'] = ''
        return None

    # only one BGP AS is supported, so we can directly send the first key
    # of the config dict
    asn = list(bgp.keys())[0]
    bgp[asn]['asn'] = asn

    # render(config) not needed, its only for debug
    render(config_file, 'frr/bgp.frr.tmpl', bgp[asn], trim_blocks=True)

    bgp['new_frr_config'] = render_to_string('frr/bgp.frr.tmpl', bgp[asn],
                                             trim_blocks=True)

    return None

def apply(bgp):
    # Save original configuration prior to starting any commit actions
    frr_cfg = {}
    frr_cfg['original_config'] = frr.get_configuration(daemon='bgpd')
    frr_cfg['modified_config'] = frr.replace_section(frr_cfg['original_config'], bgp['new_frr_config'], from_re='router bgp .*')

    # Debugging
    print('')
    print('--------- DEBUGGING ----------')
    print(f'Existing config:\n{frr_cfg["original_config"]}\n\n')
    print(f'Replacement config:\n{bgp["new_frr_config"]}\n\n')
    print(f'Modified config:\n{frr_cfg["modified_config"]}\n\n')

    # FRR mark configuration will test for syntax errors and throws an
    # exception if any syntax errors is detected
    frr.mark_configuration(frr_cfg['modified_config'])

    # Commit resulting configuration to FRR, this will throw CommitError
    # on failure
    frr.reload_configuration(frr_cfg['modified_config'], daemon='bgpd')

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
