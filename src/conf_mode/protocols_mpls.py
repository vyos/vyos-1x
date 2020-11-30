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

from sys import exit

from glob import glob
from vyos.config import Config
from vyos.configdict import node_changed
from vyos.template import render_to_string
from vyos.util import call
from vyos.util import dict_search
from vyos.util import read_file
from vyos import ConfigError
from vyos import frr
from vyos import airbag
airbag.enable()

config_file = r'/tmp/ldpd.frr'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['protocols', 'mpls']

    mpls = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    return mpls

def verify(mpls):
    # If no config, then just bail out early.
    if not mpls:
        return None

    # Checks to see if LDP is properly configured
    if 'ldp' in mpls:
        # If router ID not defined
        if 'router_id' not in mpls['ldp']:
            raise ConfigError('Router ID missing. An LDP router id is mandatory!')

        # If interface not set
        if 'interface' not in mpls['ldp']:
            raise ConfigError('LDP interfaces are missing. An LDP interface is mandatory!')

        # If transport addresses are not set
        if not dict_search('ldp.discovery.transport_ipv4_address', mpls) and \
           not dict_search('ldp.discovery.transport_ipv6_address', mpls):
                raise ConfigError('LDP transport address missing!')

    return None

def generate(mpls):
    # If there's no MPLS config generated, create dictionary key with no value.
    if not mpls:
        mpls['new_frr_config'] = ''
        return None

    mpls['new_frr_config'] = render_to_string('frr/ldpd.frr.tmpl', mpls)
    return None

def apply(mpls):
    # Define dictionary that will load FRR config
    frr_cfg = {}
    # Save original configuration prior to starting any commit actions
    frr_cfg['original_config'] = frr.get_configuration(daemon='ldpd')
    frr_cfg['modified_config'] = frr.replace_section(frr_cfg['original_config'], mpls['new_frr_config'], from_re='mpls.*')

    # If FRR config is blank, rerun the blank commit three times due to frr-reload
    # behavior/bug not properly clearing out on one commit.
    if mpls['new_frr_config'] == '':
        for x in range(3):
            frr.reload_configuration(frr_cfg['modified_config'], daemon='ldpd')
    elif not 'ldp' in mpls:
        for x in range(3):
            frr.reload_configuration(frr_cfg['modified_config'], daemon='ldpd')
    else:
        # FRR mark configuration will test for syntax errors and throws an
        # exception if any syntax errors is detected
        frr.mark_configuration(frr_cfg['modified_config'])

        # Commit resulting configuration to FRR, this will throw CommitError
        # on failure
        frr.reload_configuration(frr_cfg['modified_config'], daemon='ldpd')

    # Set number of entries in the platform label tables
    labels = '0'
    if 'interface' in mpls:
        labels = '1048575'
    call(f'sysctl -wq net.mpls.platform_labels={labels}')

    # Check for changes in global MPLS options
    if 'parameters' in mpls:
            # Choose whether to copy IP TTL to MPLS header TTL
        if 'no_propagate_ttl' in mpls['parameters']:
            call('sysctl -wq net.mpls.ip_ttl_propagate=0')
            # Choose whether to limit maximum MPLS header TTL
        if 'maximum_ttl' in mpls['parameters']:
            ttl = mpls['parameters']['maximum_ttl']
            call(f'sysctl -wq net.mpls.default_ttl={ttl}')
    else:
        # Set default global MPLS options if not defined.
        call('sysctl -wq net.mpls.ip_ttl_propagate=1')
        call('sysctl -wq net.mpls.default_ttl=255')

    # Enable and disable MPLS processing on interfaces per configuration
    if 'interface' in mpls:
        system_interfaces = []
        # Populate system interfaces list with local MPLS capable interfaces
        for interface in glob('/proc/sys/net/mpls/conf/*'):
            system_interfaces.append(os.path.basename(interface))   
        # This is where the comparison is done on if an interface needs to be enabled/disabled.
        for system_interface in system_interfaces:
            interface_state = read_file(f'/proc/sys/net/mpls/conf/{system_interface}/input')
            if '1' in interface_state:
                if system_interface not in mpls['interface']:
                    system_interface = system_interface.replace('.', '/')
                    call(f'sysctl -wq net.mpls.conf.{system_interface}.input=0')
            elif '0' in interface_state:
                if system_interface in mpls['interface']:
                    system_interface = system_interface.replace('.', '/')
                    call(f'sysctl -wq net.mpls.conf.{system_interface}.input=1')
    else:
        system_interfaces = []
        # If MPLS interfaces are not configured, set MPLS processing disabled
        for interface in glob('/proc/sys/net/mpls/conf/*'):
            system_interfaces.append(os.path.basename(interface)) 
        for system_interface in system_interfaces:
            system_interface = system_interface.replace('.', '/')
            call(f'sysctl -wq net.mpls.conf.{system_interface}.input=0')

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
