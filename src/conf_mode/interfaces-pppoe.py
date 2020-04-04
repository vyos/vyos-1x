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

import os

from sys import exit
from copy import deepcopy
from jinja2 import FileSystemLoader, Environment
from netifaces import interfaces

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos.ifconfig import Interface
from vyos.util import chown_file, chmod_x, subprocess_cmd
from vyos import ConfigError

default_config_data = {
    'access_concentrator': '',
    'auth_username': '',
    'auth_password': '',
    'on_demand': False,
    'default_route': 'auto',
    'deleted': False,
    'description': '\0',
    'disable': False,
    'intf': '',
    'idle_timeout': '',
    'ipv6_autoconf': False,
    'ipv6_enable': False,
    'local_address': '',
    'logfile': '',
    'mtu': '1492',
    'name_server': True,
    'remote_address': '',
    'service_name': '',
    'source_interface': '',
    'vrf': ''
}

def get_config():
    pppoe = deepcopy(default_config_data)
    conf = Config()
    base_path = ['interfaces', 'pppoe']

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    pppoe['intf'] = os.environ['VYOS_TAGNODE_VALUE']
    pppoe['logfile'] = f"/var/log/vyatta/ppp_{pppoe['intf']}.log"

    # Check if interface has been removed
    if not conf.exists(base_path + [pppoe['intf']]):
        pppoe['deleted'] = True
        return pppoe

    # set new configuration level
    conf.set_level(base_path + [pppoe['intf']])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['access-concentrator']):
        pppoe['access_concentrator'] = conf.return_values(['access-concentrator'])

    # Authentication name supplied to PPPoE server
    if conf.exists(['authentication', 'user']):
        pppoe['auth_username'] = conf.return_value(['authentication', 'user'])

    # Password for authenticating local machine to PPPoE server
    if conf.exists(['authentication', 'password']):
        pppoe['auth_password'] = conf.return_value(['authentication', 'password'])

    # Access concentrator name (only connect to this concentrator)
    if conf.exists(['connect-on-demand']):
        pppoe['on_demand'] = True

    # Enable/Disable default route to peer when link comes up
    if conf.exists(['default-route']):
        pppoe['default_route'] = conf.return_value(['default-route'])

    # Retrieve interface description
    if conf.exists(['description']):
        pppoe['description'] = conf.return_value(['description'])

    # Disable this interface
    if conf.exists(['disable']):
        pppoe['disable'] = True

    # Delay before disconnecting idle session (in seconds)
    if conf.exists(['idle-timeout']):
        pppoe['idle_timeout'] = conf.return_value(['idle-timeout'])

    # Enable Stateless Address Autoconfiguration (SLAAC)
    if conf.exists(['ipv6', 'address', 'autoconf']):
        pppoe['ipv6_autoconf'] = True

    # Activate IPv6 support on this connection
    if conf.exists(['ipv6', 'enable']):
        pppoe['ipv6_enable'] = True

    # IPv4 address of local end of PPPoE link
    if conf.exists(['local-address']):
        pppoe['local_address'] = conf.return_value(['local-address'])

    # Physical Interface used for this PPPoE session
    if conf.exists(['source-interface']):
        pppoe['source_interface'] = conf.return_value(['source-interface'])

    # Maximum Transmission Unit (MTU)
    if conf.exists(['mtu']):
        pppoe['mtu'] = conf.return_value(['mtu'])

    # Do not use DNS servers provided by the peer
    if conf.exists(['no-peer-dns']):
        pppoe['name_server'] = False

    # IPv4 address for remote end of PPPoE session
    if conf.exists(['remote-address']):
        pppoe['remote_address'] = conf.return_value(['remote-address'])

    # Service name, only connect to access concentrators advertising this
    if conf.exists(['service-name']):
        pppoe['service_name'] = conf.return_value(['service-name'])

    # retrieve VRF instance
    if conf.exists('vrf'):
        pppoe['vrf'] = conf.return_value(['vrf'])

    return pppoe

def verify(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['source_interface']:
        raise ConfigError('PPPoE source interface missing')

    if not pppoe['source_interface'] in interfaces():
        raise ConfigError(f"PPPoE source interface {pppoe['source_interface']} does not exist")

    vrf_name = pppoe['vrf']
    if vrf_name and vrf_name not in interfaces():
        raise ConfigError(f'VRF {vrf_name} does not exist')

    return None

def generate(pppoe):
    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir["data"], "templates", "pppoe")
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader)

    # set up configuration file path variables where our templates will be
    # rendered into
    intf = pppoe['intf']
    config_pppoe = f'/etc/ppp/peers/{intf}'
    script_pppoe_pre_up = f'/etc/ppp/ip-pre-up.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ip_up = f'/etc/ppp/ip-up.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ip_down = f'/etc/ppp/ip-down.d/1000-vyos-pppoe-{intf}'
    script_pppoe_ipv6_up = f'/etc/ppp/ipv6-up.d/1000-vyos-pppoe-{intf}'

    config_files = [config_pppoe, script_pppoe_pre_up, script_pppoe_ip_up,
                    script_pppoe_ip_down, script_pppoe_ipv6_up]

    # Ensure directories for config files exist - otherwise create them on demand
    for file in config_files:
        dirname = os.path.dirname(file)
        if not os.path.isdir(dirname):
            os.mkdir(dirname)

    # Always hang-up PPPoE connection prior generating new configuration file
    cmd = f'systemctl stop ppp@{intf}.service'
    subprocess_cmd(cmd)

    if pppoe['deleted']:
        # Delete PPP configuration files
        for file in config_files:
            if os.path.exists(file):
                os.unlink(file)

    else:
        # Create PPP configuration files
        tmpl = env.get_template('peer.tmpl')
        config_text = tmpl.render(pppoe)
        with open(config_pppoe, 'w') as f:
            f.write(config_text)

        # Create script for ip-pre-up.d
        tmpl = env.get_template('ip-pre-up.script.tmpl')
        config_text = tmpl.render(pppoe)
        with open(script_pppoe_pre_up, 'w') as f:
            f.write(config_text)

        # Create script for ip-up.d
        tmpl = env.get_template('ip-up.script.tmpl')
        config_text = tmpl.render(pppoe)
        with open(script_pppoe_ip_up, 'w') as f:
            f.write(config_text)

        # Create script for ip-down.d
        tmpl = env.get_template('ip-down.script.tmpl')
        config_text = tmpl.render(pppoe)
        with open(script_pppoe_ip_down, 'w') as f:
            f.write(config_text)

        # Create script for ipv6-up.d
        tmpl = env.get_template('ipv6-up.script.tmpl')
        config_text = tmpl.render(pppoe)
        with open(script_pppoe_ipv6_up, 'w') as f:
            f.write(config_text)

        # make generated script file executable
        chmod_x(script_pppoe_pre_up)
        chmod_x(script_pppoe_ip_up)
        chmod_x(script_pppoe_ip_down)
        chmod_x(script_pppoe_ipv6_up)

    return None

def apply(pppoe):
    if pppoe['deleted']:
        # bail out early
        return None

    if not pppoe['disable']:
        # "dial" PPPoE connection
        intf = pppoe['intf']
        cmd = f'systemctl start ppp@{intf}.service'
        subprocess_cmd(cmd)

        # make logfile owned by root / vyattacfg
        chown_file(pppoe['logfile'], 'root', 'vyattacfg')

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
