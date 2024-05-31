#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 yOS maintainers and contributors
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
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_vrf
from vyos.configverify import verify_tunnel
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import Interface
from vyos.ifconfig import TunnelIf
from vyos.utils.dict import dict_search
from vyos.utils.network import get_interface_config
from vyos.utils.network import interface_exists
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least
    the interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'tunnel']
    ifname, tunnel = get_interface_dict(conf, base)

    if 'deleted' not in tunnel:
        tmp = is_node_changed(conf, base + [ifname, 'encapsulation'])
        if tmp: tunnel.update({'encapsulation_changed': {}})

        tmp = is_node_changed(conf, base + [ifname, 'parameters', 'ip', 'key'])
        if tmp: tunnel.update({'key_changed': {}})

        # We also need to inspect other configured tunnels as there are Kernel
        # restrictions where we need to comply. E.g. GRE tunnel key can't be used
        # twice, or with multiple GRE tunnels to the same location we must specify
        # a GRE key
        conf.set_level(base)
        tunnel['other_tunnels'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                                      get_first_key=True,
                                                      no_tag_node_value_mangle=True)
        # delete our own instance from this dict
        ifname = tunnel['ifname']
        del tunnel['other_tunnels'][ifname]
        # if only one tunnel is present on the system, no need to keep this key
        if len(tunnel['other_tunnels']) == 0:
            del tunnel['other_tunnels']

    # We must check if our interface is configured to be a DMVPN member
    nhrp_base = ['protocols', 'nhrp', 'tunnel']
    conf.set_level(nhrp_base)
    nhrp = conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True)
    if nhrp: tunnel.update({'nhrp' : list(nhrp.keys())})

    if 'encapsulation' in tunnel and tunnel['encapsulation'] not in ['erspan', 'ip6erspan']:
        del tunnel['parameters']['erspan']

    return tunnel

def verify(tunnel):
    if 'deleted' in tunnel:
        verify_bridge_delete(tunnel)

        if 'nhrp' in tunnel and tunnel['ifname'] in tunnel['nhrp']:
            raise ConfigError('Tunnel used for NHRP, it can not be deleted!')

        return None

    verify_tunnel(tunnel)

    if tunnel['encapsulation'] in ['erspan', 'ip6erspan']:
        if dict_search('parameters.ip.key', tunnel) == None:
            raise ConfigError('ERSPAN requires ip key parameter!')

        # this is a default field
        ver = int(tunnel['parameters']['erspan']['version'])
        if ver == 1:
            if 'hw_id' in tunnel['parameters']['erspan']:
                raise ConfigError('ERSPAN version 1 does not support hw-id!')
            if 'direction' in tunnel['parameters']['erspan']:
                raise ConfigError('ERSPAN version 1 does not support direction!')
        elif ver == 2:
            if 'idx' in tunnel['parameters']['erspan']:
                raise ConfigError('ERSPAN version 2 does not index parameter!')
            if 'direction' not in tunnel['parameters']['erspan']:
                raise ConfigError('ERSPAN version 2 requires direction to be set!')

    # If tunnel source is any and gre key is not set
    interface = tunnel['ifname']
    if tunnel['encapsulation'] in ['gre'] and \
       dict_search('source_address', tunnel) == '0.0.0.0' and \
       dict_search('parameters.ip.key', tunnel) == None:
        raise ConfigError(f'"parameters ip key" must be set for {interface} when '\
                           'encapsulation is GRE!')

    gre_encapsulations = ['gre', 'gretap']
    if tunnel['encapsulation'] in gre_encapsulations and 'other_tunnels' in tunnel:
        # Check pairs tunnel source-address/encapsulation/key with exists tunnels.
        # Prevent the same key for 2 tunnels with same source-address/encap. T2920
        for o_tunnel, o_tunnel_conf in tunnel['other_tunnels'].items():
            # no match on encapsulation - bail out
            our_encapsulation = tunnel['encapsulation']
            their_encapsulation = o_tunnel_conf['encapsulation']
            if our_encapsulation in gre_encapsulations and their_encapsulation \
                not in gre_encapsulations:
                continue

            our_address = dict_search('source_address', tunnel)
            our_key = dict_search('parameters.ip.key', tunnel)
            their_address = dict_search('source_address', o_tunnel_conf)
            their_key = dict_search('parameters.ip.key', o_tunnel_conf)
            if our_key != None:
                if their_address == our_address and their_key == our_key:
                    raise ConfigError(f'Key "{our_key}" for source-address "{our_address}" ' \
                                      f'is already used for tunnel "{o_tunnel}"!')
            else:
                our_source_if = dict_search('source_interface', tunnel)
                their_source_if = dict_search('source_interface', o_tunnel_conf)
                our_remote = dict_search('remote', tunnel)
                their_remote = dict_search('remote', o_tunnel_conf)
                # If no IP GRE key is defined we can not have more then one GRE tunnel
                # bound to any one interface/IP address and the same remote. This will
                # result in a OS  PermissionError: add tunnel "gre0" failed: File exists
                if our_remote == their_remote:
                    if our_address is not None and their_address == our_address: 
                        # If set to the same values, this is always a fail 
                        raise ConfigError(f'Missing required "ip key" parameter when '\
                                           'running more then one GRE based tunnel on the '\
                                           'same source-address')

                    if their_source_if == our_source_if and their_address == our_address:
                        # Note that lack of None check on these is deliberate. 
                        # source-if and source-ip matching while unset (all None) is a fail
                        # source-ifs set and matching with unset source-ips is a fail
                        raise ConfigError(f'Missing required "ip key" parameter when '\
                                           'running more then one GRE based tunnel on the '\
                                           'same source-interface')

    # Keys are not allowed with ipip and sit tunnels
    if tunnel['encapsulation'] in ['ipip', 'sit']:
        if dict_search('parameters.ip.key', tunnel) != None:
            raise ConfigError('Keys are not allowed with ipip and sit tunnels!')

    verify_mtu_ipv6(tunnel)
    verify_address(tunnel)
    verify_vrf(tunnel)
    verify_bond_bridge_member(tunnel)
    verify_mirror_redirect(tunnel)

    if 'source_interface' in tunnel:
        verify_source_interface(tunnel)

    # TTL != 0 and nopmtudisc are incompatible, parameters and ip use default
    # values, thus the keys are always present.
    if dict_search('parameters.ip.no_pmtu_discovery', tunnel) != None:
        if dict_search('parameters.ip.ttl', tunnel) != '0':
            raise ConfigError('Disabled PMTU requires TTL set to "0"!')
        if tunnel['encapsulation'] in ['ipip6', 'ip6ip6', 'ip6gre']:
            raise ConfigError('Can not disable PMTU discovery for given encapsulation')

    if dict_search('parameters.ip.ignore_df', tunnel) != None:
        if tunnel['encapsulation'] not in ['gretap']:
            raise ConfigError('Option ignore-df can only be used on GRETAP tunnels!')

        if dict_search('parameters.ip.no_pmtu_discovery', tunnel) == None:
            raise ConfigError('Option ignore-df requires path MTU discovery to be disabled!')


def generate(tunnel):
    return None

def apply(tunnel):
    interface = tunnel['ifname']
    # If a gretap tunnel is already existing we can not "simply" change local or
    # remote addresses. This returns "Operation not supported" by the Kernel.
    # There is no other solution to destroy and recreate the tunnel.
    encap = ''
    remote = ''
    tmp = get_interface_config(interface)
    if tmp:
        encap = dict_search('linkinfo.info_kind', tmp)
        remote = dict_search('linkinfo.info_data.remote', tmp)

    if ('deleted' in tunnel or 'encapsulation_changed' in tunnel or encap in
        ['gretap', 'ip6gretap', 'erspan', 'ip6erspan'] or remote in ['any'] or
        'key_changed' in tunnel):
        if interface_exists(interface):
            tmp = Interface(interface)
            tmp.remove()
        if 'deleted' in tunnel:
            return None

    tun = TunnelIf(**tunnel)
    tun.update(tunnel)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        generate(c)
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
