#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_authentication
from vyos.configverify import verify_vrf
from vyos.ifconfig import SSTPCIf
from vyos.pki import encode_certificate
from vyos.pki import find_chain
from vyos.pki import load_certificate
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.dict import dict_search
from vyos.utils.process import is_systemd_service_running
from vyos.utils.file import write_file
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'sstpc']
    ifname, sstpc = get_interface_dict(conf, base, with_pki=True)

    # We should only terminate the SSTP client session if critical parameters
    # change. All parameters that can be changed on-the-fly (like interface
    # description) should not lead to a reconnect!
    for options in ['authentication', 'no_peer_dns', 'no_default_route',
                    'server', 'ssl']:
        if is_node_changed(conf, base + [ifname, options]):
            sstpc.update({'shutdown_required': {}})
            # bail out early - no need to further process other nodes
            break

    return sstpc

def verify(sstpc):
    if 'deleted' in sstpc:
        return None

    verify_authentication(sstpc)
    verify_vrf(sstpc)

    if not dict_search('server', sstpc):
        raise ConfigError('Remote SSTP server must be specified!')

    if not dict_search('ssl.ca_certificate', sstpc):
        raise ConfigError('Missing mandatory CA certificate!')

    return None

def generate(sstpc):
    ifname = sstpc['ifname']
    config_sstpc = f'/etc/ppp/peers/{ifname}'

    sstpc['ca_file_path'] = f'/run/sstpc/{ifname}_ca-cert.pem'

    if 'deleted' in sstpc:
        for file in [sstpc['ca_file_path'], config_sstpc]:
            if os.path.exists(file):
                os.unlink(file)
        return None

    ca_name = sstpc['ssl']['ca_certificate']
    pki_ca_cert = sstpc['pki']['ca'][ca_name]

    loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
    loaded_ca_certs = {load_certificate(c['certificate'])
            for c in sstpc['pki']['ca'].values()} if 'ca' in sstpc['pki'] else {}

    ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)

    write_file(sstpc['ca_file_path'], '\n'.join(encode_certificate(c) for c in ca_full_chain))
    render(config_sstpc, 'sstp-client/peer.j2', sstpc, permission=0o640)

    return None

def apply(sstpc):
    ifname = sstpc['ifname']
    if 'deleted' in sstpc or 'disable' in sstpc:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = SSTPCIf(ifname)
            p.remove()
        call(f'systemctl stop ppp@{ifname}.service')
        return None

    # reconnect should only be necessary when specific options change,
    # like server, authentication ... (see get_config() for details)
    if ((not is_systemd_service_running(f'ppp@{ifname}.service')) or
        'shutdown_required' in sstpc):

        # cleanup system (e.g. FRR routes first)
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = SSTPCIf(ifname)
            p.remove()

        call(f'systemctl restart ppp@{ifname}.service')
        # When interface comes "live" a hook is called:
        # /etc/ppp/ip-up.d/96-vyos-sstpc-callback
        # which triggers SSTPCIf.update()
    else:
        if os.path.isdir(f'/sys/class/net/{ifname}'):
            p = SSTPCIf(ifname)
            p.update(sstpc)

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
