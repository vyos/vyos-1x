# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
Library used to interface with FRRs mgmtd introduced in version 10.0
"""

import os

from vyos.defaults import frr_debug_enable
from vyos.utils.file import write_file
from vyos.utils.process import cmd
from vyos.utils.process import rc_cmd
from vyos.template import render_to_string
from vyos import ConfigError

DEBUG_ON = os.path.exists(frr_debug_enable)

def debug(message):
    if not DEBUG_ON:
        return
    print(message)

frr_protocols = ['babel', 'bfd', 'bgp', 'eigrp', 'isis', 'mpls', 'nhrp',
                 'openfabric', 'ospf', 'ospfv3', 'pim', 'pim6', 'rip',
                 'ripng', 'rpki', 'segment_routing', 'static']

babel_daemon = 'babeld'
bfd_daemon = 'bfdd'
bgp_daemon = 'bgpd'
isis_daemon = 'isisd'
ldpd_daemon = 'ldpd'
mgmt_daemon = 'mgmtd'
openfabric_daemon = 'fabricd'
ospf_daemon = 'ospfd'
ospf6_daemon = 'ospf6d'
pim_daemon = 'pimd'
pim6_daemon = 'pim6d'
rip_daemon = 'ripd'
ripng_daemon = 'ripngd'
zebra_daemon = 'zebra'

class FRRender:
    def __init__(self):
        self._frr_conf = '/run/frr/config/vyos.frr.conf'

    def generate(self, config):
        if not isinstance(config, dict):
            tmp = type(config)
            raise ValueError(f'Config must be of type "dict" and not "{tmp}"!')

        def inline_helper(config_dict) -> str:
            output = '!\n'
            if 'babel' in config_dict and 'deleted' not in config_dict['babel']:
                output += render_to_string('frr/babeld.frr.j2', config_dict['babel'])
                output += '\n'
            if 'bfd' in config_dict and 'deleted' not in config_dict['bfd']:
                output += render_to_string('frr/bfdd.frr.j2', config_dict['bfd'])
                output += '\n'
            if 'bgp' in config_dict and 'deleted' not in config_dict['bgp']:
                output += render_to_string('frr/bgpd.frr.j2', config_dict['bgp'])
                output += '\n'
            if 'eigrp' in config_dict and 'deleted' not in config_dict['eigrp']:
                output += render_to_string('frr/eigrpd.frr.j2', config_dict['eigrp'])
                output += '\n'
            if 'isis' in config_dict and 'deleted' not in config_dict['isis']:
                output += render_to_string('frr/isisd.frr.j2', config_dict['isis'])
                output += '\n'
            if 'mpls' in config_dict and 'deleted' not in config_dict['mpls']:
                output += render_to_string('frr/ldpd.frr.j2', config_dict['mpls'])
                output += '\n'
            if 'openfabric' in config_dict and 'deleted' not in config_dict['openfabric']:
                output += render_to_string('frr/fabricd.frr.j2', config_dict['openfabric'])
                output += '\n'
            if 'ospf' in config_dict and 'deleted' not in config_dict['ospf']:
                output += render_to_string('frr/ospfd.frr.j2', config_dict['ospf'])
                output += '\n'
            if 'ospfv3' in config_dict and 'deleted' not in config_dict['ospfv3']:
                output += render_to_string('frr/ospf6d.frr.j2', config_dict['ospfv3'])
                output += '\n'
            if 'pim' in config_dict and 'deleted' not in config_dict['pim']:
                output += render_to_string('frr/pimd.frr.j2', config_dict['pim'])
                output += '\n'
            if 'pim6' in config_dict and 'deleted' not in config_dict['pim6']:
                output += render_to_string('frr/pim6d.frr.j2', config_dict['pim6'])
                output += '\n'
            if 'policy' in config_dict and len(config_dict['policy']) > 0:
                output += render_to_string('frr/policy.frr.j2', config_dict['policy'])
                output += '\n'
            if 'rip' in config_dict and 'deleted' not in config_dict['rip']:
                output += render_to_string('frr/ripd.frr.j2', config_dict['rip'])
                output += '\n'
            if 'ripng' in config_dict and 'deleted' not in config_dict['ripng']:
                output += render_to_string('frr/ripngd.frr.j2', config_dict['ripng'])
                output += '\n'
            if 'rpki' in config_dict and 'deleted' not in config_dict['rpki']:
                output += render_to_string('frr/rpki.frr.j2', config_dict['rpki'])
                output += '\n'
            if 'segment_routing' in config_dict and 'deleted' not in config_dict['segment_routing']:
                output += render_to_string('frr/zebra.segment_routing.frr.j2', config_dict['segment_routing'])
                output += '\n'
            if 'static' in config_dict and 'deleted' not in config_dict['static']:
                output += render_to_string('frr/staticd.frr.j2', config_dict['static'])
                output += '\n'
            if 'ip' in config_dict and 'deleted' not in config_dict['ip']:
                output += render_to_string('frr/zebra.route-map.frr.j2', config_dict['ip'])
                output += '\n'
            if 'ipv6' in config_dict and 'deleted' not in config_dict['ipv6']:
                output += render_to_string('frr/zebra.route-map.frr.j2', config_dict['ipv6'])
                output += '\n'
            return output

        debug('======< RENDERING CONFIG >======')
        # we can not reload an empty file, thus we always embed the marker
        output = '!\n'
        # Enable SNMP agentx support
        # SNMP AgentX support cannot be disabled once enabled
        if 'snmp' in config:
            output += 'agentx\n'
        # Add routing protocols in global VRF
        output += inline_helper(config)
        # Interface configuration for EVPN is not VRF related
        if 'interfaces' in config:
            output += render_to_string('frr/evpn.mh.frr.j2', {'interfaces' : config['interfaces']})
            output += '\n'

        if 'vrf' in config and 'name' in config['vrf']:
            output += render_to_string('frr/zebra.vrf.route-map.frr.j2', config['vrf'])
            for vrf, vrf_config in config['vrf']['name'].items():
                if 'protocols' not in vrf_config:
                    continue
                for protocol in vrf_config['protocols']:
                    vrf_config['protocols'][protocol]['vrf'] = vrf

                output += inline_helper(vrf_config['protocols'])

        # remove any accidently added empty newline to not confuse FRR
        output = os.linesep.join([s for s in output.splitlines() if s])

        if '!!' in output:
            raise ConfigError('FRR configuration contains "!!" which is not allowed')

        debug(output)
        debug('======< RENDERING CONFIG COMPLETE >======')
        write_file(self._frr_conf, output)

    def apply(self, count_max=5):
        count = 0
        emsg = ''
        while count < count_max:
            count += 1
            debug(f'FRR: Reloading configuration - tries: {count} | Python class ID: {id(self)}')
            cmdline = '/usr/lib/frr/frr-reload.py --reload'
            if DEBUG_ON: cmdline += ' --debug'
            try:
                rc, emsg = rc_cmd(f'{cmdline} {self._frr_conf}')
                if rc != 0:
                    continue
                debug(emsg)
                debug('======< DONE APPLYING CONFIG  >======')
                break
            except:
                continue
        if count >= count_max:
            raise ConfigError(emsg)

        # T3217: Save FRR configuration to /run/frr/config/frr.conf
        return cmd('/usr/bin/vtysh -n --writeconfig')
