#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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
from shutil import rmtree

from sys import exit

from netifaces import AF_INET
from psutil import net_if_addrs

from vyos.config import Config
from vyos.configverify import verify_pki_ca_certificate
from vyos.configverify import verify_pki_certificate
from vyos.pki import encode_certificate
from vyos.pki import encode_private_key
from vyos.pki import find_chain
from vyos.pki import load_certificate
from vyos.pki import load_private_key
from vyos.utils.dict import dict_search
from vyos.utils.file import makedir
from vyos.utils.file import write_file
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.process import call
from vyos.template import render
from vyos import ConfigError
from vyos import airbag
airbag.enable()

stunnel_dir = '/run/stunnel'
config_file = f'{stunnel_dir}/stunnel.conf'
stunnel_ca_dir = f'{stunnel_dir}/ca'
stunnel_psk_dir = f'{stunnel_dir}/psk'

# config based on
# http://man.he.net/man8/stunnel4


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'stunnel']
    if not conf.exists(base):
        return None

    stunnel = conf.get_config_dict(base,
                              get_first_key=True,
                              key_mangling=('-', '_'),
                              no_tag_node_value_mangle=True,
                              with_recursive_defaults=True,
                              with_pki=True)
    stunnel['config_file'] = config_file
    return stunnel


def verify(stunnel):
    if not stunnel:
        return None

    stunnel_listen_addresses = list()
    for mode, conf in stunnel.items():
        if mode not in ['server', 'client']:
            continue

        for app, app_conf in conf.items():
            # connect, listen, exec and some protocols e.g. socks on server mode are endpoints.
            endpoints = 0
            if 'socks' == app_conf.get('protocol') and mode == 'server':
                if 'connect' in app_conf:
                    raise ConfigError("The 'connect' option cannot be used with the 'socks' protocol in server mode.")
                endpoints += 1

            for item in ['connect', 'listen']:
                if item in app_conf:
                    endpoints += 1
                    if 'port' not in app_conf[item]:
                        raise ConfigError(f'{mode} [{app}]: {item} port number is required!')
                elif item == 'listen':
                    raise ConfigError(f'{mode} [{app}]: {item} port number is required!')

            if endpoints != 2:
                raise ConfigError(f'{mode} [{app}]: connect port number is required!')

            if 'address' in app_conf['listen']:
                laddresses = [dict_search('listen.address', app_conf)]
            else:
                laddresses = list()
                ifaces = net_if_addrs()
                for iface_name, iface_addresses in ifaces.items():
                    for iface_addr in iface_addresses:
                        if iface_addr.family == AF_INET:
                            laddresses.append(iface_addr.address)

            lport = int(dict_search('listen.port', app_conf))

            for address in laddresses:
                if f'{address}:{lport}' in stunnel_listen_addresses:
                    raise ConfigError(
                        f'{mode} [{app}]: Address {address}:{lport} already '
                        f'in use by other stunnel service')

                stunnel_listen_addresses.append(f'{address}:{lport}')
                if not check_port_availability(address, lport, 'tcp') and \
                not is_listen_port_bind_service(lport, 'stunnel'):
                    raise ConfigError(
                        f'{mode} [{app}]: Address {address}:{lport} already in use')

            if 'options' in app_conf:
                protocol = app_conf.get('protocol')
                if protocol not in ['connect', 'smtp']:
                    raise ConfigError("Additional option is only supported in the 'connect' and 'smtp' protocols.")
                if protocol == 'smtp' and ('domain' in app_conf['options'] or 'host' in app_conf['options']):
                    raise ConfigError("Protocol 'smtp' does not support options 'domain' and 'host'.")

                # set default authentication option
                if 'authentication' not in app_conf['options']:
                    app_conf['options']['authentication'] = 'basic' if protocol == 'connect' else 'plain'

                for option, option_config in app_conf['options'].items():
                    if option == 'authentication':
                        if protocol == 'connect' and option_config not in ['basic', 'ntlm']:
                            raise ConfigError("Supported authentication types for the 'connect' protocol are 'basic' or 'ntlm'")
                        elif protocol == 'smtp' and option_config not in ['plain', 'login']:
                            raise ConfigError("Supported authentication types for the 'smtp' protocol are 'plain' or 'login'")
                    if option == 'host':
                        if 'address' not in option_config:
                            raise ConfigError('Address is required for option host.')
                        if 'port' not in option_config:
                            raise ConfigError('Port is required for option host.')

            # check pki certs
            for key in ['ca_certificate', 'certificate']:
                tmp = dict_search(f'ssl.{key}', app_conf)
                if mode == 'server' and key != 'ca_certificate' and not tmp and 'psk' not in app_conf:
                    raise ConfigError(f'{mode} [{app}]: TLS server needs a certificate or PSK')
                if tmp:
                    if key == 'ca_certificate':
                        for ca_cert in tmp:
                            verify_pki_ca_certificate(stunnel, ca_cert)
                    else:
                        verify_pki_certificate(stunnel, tmp)

            #check psk
            if 'psk' in app_conf:
                for psk, psk_conf in app_conf['psk'].items():
                    if 'id' not in psk_conf or 'secret' not in psk_conf:
                        raise ConfigError(
                            f'Authentication psk "{psk}" missing "id" or "secret"')


def generate(stunnel):
    if not stunnel or ('client' not in stunnel and 'server' not in stunnel):
        if os.path.isdir(stunnel_dir):
            rmtree(stunnel_dir, ignore_errors=True)

        return None
    makedir(stunnel_dir)

    exist_files = list()
    current_files = [config_file, config_file.replace('.conf', 'pid')]
    for root, dirs, files in os.walk(stunnel_dir):
        for file in files:
            exist_files.append(os.path.join(root, file))

    loaded_ca_certs = {load_certificate(c['certificate'])
        for c in stunnel['pki']['ca'].values()} if 'pki' in stunnel and 'ca' in stunnel['pki'] else {}

    for mode, conf in stunnel.items():
        if mode not in ['server', 'client']:
            continue

        for app, app_conf in conf.items():
            if 'ssl' in app_conf:
                if 'certificate' in app_conf['ssl']:
                    cert_name = app_conf['ssl']['certificate']

                    pki_cert = stunnel['pki']['certificate'][cert_name]
                    cert_file_path = os.path.join(stunnel_dir,
                                                  f'{mode}-{app}-{cert_name}.pem')
                    cert_key_path = os.path.join(stunnel_dir,
                                                 f'{mode}-{app}-{cert_name}.pem.key')
                    app_conf['ssl']['cert'] = cert_file_path

                    loaded_pki_cert = load_certificate(pki_cert['certificate'])
                    cert_full_chain = find_chain(loaded_pki_cert, loaded_ca_certs)

                    write_file(cert_file_path,
                       '\n'.join(encode_certificate(c) for c in cert_full_chain))
                    current_files.append(cert_file_path)

                    if 'private' in pki_cert and 'key' in pki_cert['private']:
                        app_conf['ssl']['cert_key'] = cert_key_path
                        loaded_key = load_private_key(pki_cert['private']['key'],
                                                      passphrase=None, wrap_tags=True)
                        key_pem = encode_private_key(loaded_key, passphrase=None)
                        write_file(cert_key_path, key_pem, mode=0o600)
                        current_files.append(cert_key_path)

                if 'ca_certificate' in app_conf['ssl']:
                    app_conf['ssl']['ca_path'] = stunnel_ca_dir
                    app_conf['ssl']['ca_file'] = f'{mode}-{app}-ca.pem'
                    ca_cert_file_path = os.path.join(stunnel_ca_dir, app_conf['ssl']['ca_file'])
                    ca_chains = []

                    for ca_name in app_conf['ssl']['ca_certificate']:
                        pki_ca_cert = stunnel['pki']['ca'][ca_name]
                        loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
                        ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)
                        ca_chains.append(
                            '\n'.join(encode_certificate(c) for c in ca_full_chain))

                    write_file(ca_cert_file_path, '\n'.join(ca_chains))
                    current_files.append(ca_cert_file_path)

            if 'psk' in app_conf:
                psk_data = list()
                psk_file_path = os.path.join(stunnel_psk_dir, f'{mode}_{app}.txt')

                for _, psk_conf in app_conf['psk'].items():
                    psk_data.append(f'{psk_conf["id"]}:{psk_conf["secret"]}')

                write_file(psk_file_path, '\n'.join(psk_data))
                app_conf['psk']['file'] = psk_file_path
                current_files.append(psk_file_path)

    for file in exist_files:
        if file not in current_files:
            os.unlink(file)

    render(config_file, 'stunnel/stunnel_config.j2', stunnel)


def apply(stunnel):
    if not stunnel or ('client' not in stunnel and 'server' not in stunnel):
        call('systemctl stop stunnel.service')
    else:
        call('systemctl restart stunnel.service')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
