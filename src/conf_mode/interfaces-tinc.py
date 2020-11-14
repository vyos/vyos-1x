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

import os
import shutil

from sys import exit
from copy import deepcopy

from netifaces import interfaces
from vyos.configdict import get_interface_dict,leaf_node_changed
from vyos.config import Config
from time import sleep
from vyos.ifconfig import TincIf
from vyos import ConfigError
from vyos.util import call
from vyos.xml import defaults
from vyos.configdict import dict_merge
from vyos.template import render
from vyos.configverify import verify_address
from vyos.configverify import verify_dhcpv6
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mtu
from vyos.configverify import verify_mtu_ipv6
from vyos.configverify import verify_vlan_config
from vyos.configverify import verify_vrf

from vyos import airbag

airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
        
    base = ['interfaces', 'tinc']
    
    tinc = get_interface_dict(conf, base)
    
    if 'network_dir' in tinc:
        tinc_network_dir=tinc['network_dir']
        ed25516_private_key = f'{tinc_network_dir}/ed25519_key.priv'
        rsa_private_key = f'{tinc_network_dir}/rsa_key.priv'
        tinc.update({'ed25516_private_key':ed25516_private_key,'rsa_private_key':rsa_private_key});
    
    if 'deleted' in tinc:
        tmp = leaf_node_changed(conf, ['network-dir'])
        if tmp and len(tmp) == 1:
            tinc.update({'network_dir':tmp[0]})
    
    return tinc

def verify(tinc):
    #bail out early - looks like removal from running config
    if tinc is None:
        return None
    network = tinc['ifname']
    if 'deleted' in tinc or 'disable' in tinc:
        return None
    if 'address' not in tinc:
        raise ConfigError('address must be set')
    if 'network_dir' not in tinc:
        tinc.update({'network_dir': f'/config/tinc/{network}'})
    if 'subnets' not in tinc:
        raise ConfigError('subnets must be set')
    if 'node_name' not in tinc:
        raise ConfigError('node_name must be set')
    if 'connect' in tinc:
        node_name=tinc['node_name']
        connect_peer_node_name=tinc['connect']
        if node_name == connect_peer_node_name:
            raise ConfigError('The local node name("{local_node}") and the remote target connection node name("{remote_node}") cannot match'.format(local_node=node_name,remote_node=connect_peer_node_name))
    
    if 'proxy' in tinc:
        if 'address' not in tinc['proxy']:
            raise ConfigError('proxy.address must be set')
        if 'port' not in tinc['proxy']:
            raise ConfigError('proxy.port must be set')
        if 'type' not in tinc['proxy']:
            raise ConfigError('proxy.type must be set')
        if tinc['proxy']['type'] == 'socks5': 
            if 'password' not in tinc['proxy']:
                raise ConfigError('proxy.password must be set')
        if tinc['proxy']['type'] == 'socks4' or tinc['proxy']['type'] == 'socks5':            
            if 'username' not in tinc['proxy']:
                raise ConfigError('proxy.username must be set')
        if tinc['proxy']['type'] == 'exec':
            if 'exec' not in tinc:
                raise ConfigError('proxy.exec must be set')
    
    if 'connect' in tinc:
        for conn in tinc['connect']:
            if 'conf_path' in tinc['connect'][conn] and not os.path.exists(tinc['connect'][conn]['conf_path']):
                raise ConfigError('The configuration file connected to peer {peer} is missing'.format(peer=conn))
    
    verify_dhcpv6(tinc)
    verify_address(tinc)
    verify_vrf(tinc)
    
    if {'is_bond_member', 'mac'} <= set(tinc):
        print(f'WARNING: changing mac address "{mac}" will be ignored as "{ifname}" '
              f'is a member of bond "{is_bond_member}"'.format(**tinc))
    
    return None

def create_or_delete_network(tinc,op):
    if tinc is None:
        return None
    interface = tinc['ifname']
    network = tinc['ifname']
    system_network_dir=f'/etc/tinc/{network}'
    tinc_network_dir=tinc['network_dir']
    if tinc:
        if op == "delete":
            if os.path.exists(system_network_dir):
                shutil.rmtree(system_network_dir)
            if os.path.exists(tinc_network_dir):
                shutil.rmtree(tinc_network_dir)
        elif op == 'create':
            if not os.path.exists(tinc_network_dir):
                os.makedirs(tinc_network_dir, mode=0o666 )
            if not os.path.exists(f'{tinc_network_dir}/hosts'):
                os.makedirs(f'{tinc_network_dir}/hosts', mode=0o666 )
            if not os.path.exists(system_network_dir):
                os.makedirs(system_network_dir, mode=0o666 )
            call(f'chown vyos -R {tinc_network_dir}')
            call(f'chown vyos -R {system_network_dir}')
            call(f'chmod a+x -R {tinc_network_dir}')
            call(f'chmod a+x -R {system_network_dir}')
            if not os.path.exists(f'{system_network_dir}/hosts'):
                os.symlink(f'{tinc_network_dir}/hosts',f'{system_network_dir}/hosts')
    return None

def generate(tinc):
    if tinc is None:
        return None
    if 'deleted' in tinc or 'disable' in tinc:
        return None
    interface = tinc['ifname']
    network = tinc['ifname']
    node_name=tinc['node_name']
    keys_length = tinc['keys_length']
    tinc_network_dir=tinc['network_dir']
    rsa_private_keyfile = f'{tinc_network_dir}/rsa_key.priv'
    ed25519_private_keyfile = f'{tinc_network_dir}/ed25519_key.priv'
    tinc_hosts_dir=f'/{tinc_network_dir}/hosts'
    system_network_dir=f'/etc/tinc/{network}'
    tinc_main_config=f'{system_network_dir}/tinc.conf'
    tinc_host_local_peer_config=f'{tinc_network_dir}/hosts/{node_name}'
    if tinc:
        if not os.path.exists(system_network_dir) or not os.path.exists(tinc_network_dir):
            create_or_delete_network(tinc,'create') # Create a directory
        call(f'tinc -b -n {network} init {node_name}')
        if not os.path.exists(rsa_private_keyfile) and not os.path.exists(ed25519_private_keyfile) and not os.path.exists(tinc_host_local_peer_config) :
            render(tinc_host_local_peer_config, 'tinc/hosts_config.tmpl', tinc)
            call(f'tinc -b -n {network} generate-keys {keys_length}')
            shutil.move(f'{system_network_dir}/ed25519_key.priv',f'{tinc_network_dir}/ed25519_key.priv')
            shutil.move(f'{system_network_dir}/rsa_key.priv',f'{tinc_network_dir}/rsa_key.priv')
        elif not os.path.exists(rsa_private_keyfile) or not os.path.exists(ed25519_private_keyfile) or not os.path.exists(tinc_host_local_peer_config):
            if os.path.exists(rsa_private_keyfile):
                os.remove(rsa_private_keyfile)
            if os.path.exists(ed25519_private_keyfile):
                os.remove(ed25519_private_keyfile)
            if os.path.exists(tinc_host_local_peer_config):
                os.remove(tinc_host_local_peer_config)
            render(tinc_host_local_peer_config, 'tinc/hosts_config.tmpl', tinc)
            call(f'tinc -b -n {network} generate-keys {keys_length}')
            shutil.move(f'{system_network_dir}/ed25519_key.priv',f'{tinc_network_dir}/ed25519_key.priv')
            shutil.move(f'{system_network_dir}/rsa_key.priv',f'{tinc_network_dir}/rsa_key.priv')
        else:
            try:
                call(f'tinc -n {network} del subnet')
                call(f'tinc -n {network} del address')
                call(f'tinc -n {network} del port')
                if 'subnets' in tinc:
                    for subnet in tinc['subnets']:
                        call(f'tinc -n {network} add subnet {subnet}')
                if 'local_address' in tinc:
                    for address in tinc['local_address']:
                        call(f'tinc -n {network} add address {address}')
                port = tinc['port']
                call(f'tinc -n {network} add port {port}')
            except:
                pass
        render(tinc_main_config, 'tinc/tinc.conf.tmpl', tinc)
        if 'connect' in tinc:
            for conn in tinc['connect']:
                if 'conf_path' in tinc['connect'][conn]:
                    conf = f'{tinc_hosts_dir}/{conn}'
                    system_conf = f'{system_network_dir}/hosts/{conn}'
                    if tinc['connect'][conn]['conf_path'] != conf and tinc['connect'][conn]['conf_path'] != system_conf:
                        base = tinc['connect'][conn]['conf_path']
                        tmp = f'/tmp/remote_tinc_{conn}'
                        os.symlink(base,conf)
            
    return None

def apply(tinc):
    if tinc is None:
        return None
    interface = tinc['ifname']
    if 'deleted' in tinc or 'disable' in tinc:
        network = tinc['ifname']
        call(f'systemctl stop tinc@{network}')
        if 'deleted' in tinc:
            create_or_delete_network(tinc,'delete') # Delete a directory
        try:
            t = TincIf(interface)
            # Delete Interface
            t.remove()
        except:
            pass
    else:
        network = tinc['ifname']
        call(f'systemctl restart tinc@{network}')
        
        # sleep 250ms
        sleep(0.250)
        try:
            t = TincIf(interface)
            #update interface description used e.g. within SNMP
            t.update(tinc)
        except:
            pass


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
