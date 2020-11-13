#!/usr/bin/env python3
#
# Copyright (C) 2019-2020 VyOS maintainers and contributors
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
import re

from sys import exit
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import IPv6Address
from ipaddress import IPv6Network
from ipaddress import summarize_address_range
from netifaces import interfaces
from shutil import rmtree

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_diffie_hellman_length
from vyos.ifconfig import VTunIf
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.util import call
from vyos.util import chown
from vyos.util import chmod_600
from vyos.util import dict_search
from vyos.validate import is_addr_assigned

from vyos import ConfigError
from vyos import airbag
airbag.enable()

user = 'openvpn'
group = 'openvpn'

cfg_file = '/run/openvpn/{ifname}.conf'

def checkCertHeader(header, filename):
    """
    Verify if filename contains specified header.
    Returns True if match is found, False if no match or file is not found
    """
    if not os.path.isfile(filename):
        return False

    with open(filename, 'r') as f:
        for line in f:
            if re.match(header, line):
                return True

    return False

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'openvpn']
    openvpn = get_interface_dict(conf, base)

    openvpn['auth_user_pass_file'] = '/run/openvpn/{ifname}.pw'.format(**openvpn)
    openvpn['daemon_user'] = user
    openvpn['daemon_group'] = group

    return openvpn

def verify(openvpn):
    if 'deleted' in openvpn:
        verify_bridge_delete(openvpn)
        return None

    if 'mode' not in openvpn:
        raise ConfigError('Must specify OpenVPN operation mode!')

    # Check if we have disabled ncp and at the same time specified ncp-ciphers
    if 'encryption' in openvpn:
        if {'disable_ncp', 'ncp_ciphers'} <= set(openvpn.get('encryption')):
            raise ConfigError('Can not specify both "encryption disable-ncp" '\
                              'and "encryption ncp-ciphers"')

    #
    # OpenVPN client mode - VERIFY
    #
    if openvpn['mode'] == 'client':
        if 'local_port' in openvpn:
            raise ConfigError('Cannot specify "local-port" in client mode')

        if 'local_host' in openvpn:
            raise ConfigError('Cannot specify "local-host" in client mode')

        if 'remote_host' not in openvpn:
            raise ConfigError('Must specify "remote-host" in client mode')

        if openvpn['protocol'] == 'tcp-passive':
            raise ConfigError('Protocol "tcp-passive" is not valid in client mode')

        if dict_search('tls.dh_file', openvpn):
            raise ConfigError('Cannot specify "tls dh-file" in client mode')

    #
    # OpenVPN site-to-site - VERIFY
    #
    elif openvpn['mode'] == 'site-to-site':
        if not 'local_address' in openvpn:
            raise ConfigError('Must specify "local-address" or add interface to bridge')

        if len([addr for addr in openvpn['local_address'] if is_ipv4(addr)]) > 1:
            raise ConfigError('Only one IPv4 local-address can be specified')

        if len([addr for addr in openvpn['local_address'] if is_ipv6(addr)]) > 1:
            raise ConfigError('Only one IPv6 local-address can be specified')

        if openvpn['device_type'] == 'tun':
            if 'remote_address' not in openvpn:
                raise ConfigError('Must specify "remote-address"')

        if 'remote_address' in openvpn:
            if len([addr for addr in openvpn['remote_address'] if is_ipv4(addr)]) > 1:
                raise ConfigError('Only one IPv4 remote-address can be specified')

            if len([addr for addr in openvpn['remote_address'] if is_ipv6(addr)]) > 1:
                raise ConfigError('Only one IPv6 remote-address can be specified')

            if not 'local_address' in openvpn:
                raise ConfigError('"remote-address" requires "local-address"')

            v4loAddr = [addr for addr in openvpn['local_address'] if is_ipv4(addr)]
            v4remAddr = [addr for addr in openvpn['remote_address'] if is_ipv4(addr)]
            if v4loAddr and not v4remAddr:
                raise ConfigError('IPv4 "local-address" requires IPv4 "remote-address"')
            elif v4remAddr and not v4loAddr:
                raise ConfigError('IPv4 "remote-address" requires IPv4 "local-address"')

            v6remAddr = [addr for addr in openvpn['remote_address'] if is_ipv6(addr)]
            v6loAddr = [addr for addr in openvpn['local_address'] if is_ipv6(addr)]
            if v6loAddr and not v6remAddr:
                raise ConfigError('IPv6 "local-address" requires IPv6 "remote-address"')
            elif v6remAddr and not v6loAddr:
                raise ConfigError('IPv6 "remote-address" requires IPv6 "local-address"')

            if (v4loAddr == v4remAddr) or (v6remAddr == v4remAddr):
                raise ConfigError('"local-address" and "remote-address" cannot be the same')

            if dict_search('local_host', openvpn) in dict_search('local_address', openvpn):
                raise ConfigError('"local-address" cannot be the same as "local-host"')

            if dict_search('remote_host', openvpn) in dict_search('remote_address', openvpn):
                raise ConfigError('"remote-address" and "remote-host" can not be the same')


        if 'local_address' in openvpn:
            # we can only have one local_address, this is ensured above
            v4addr = None
            for laddr in openvpn['local_address']:
                if is_ipv4(laddr): v4addr = laddr

            if 'remote_address' not in openvpn and (v4addr not in openvpn['local_address'] or 'subnet_mask' not in openvpn['local_address'][v4addr]):
                raise ConfigError('IPv4 "local-address" requires IPv4 "remote-address" or IPv4 "local-address subnet"')

        if dict_search('encryption.ncp_ciphers', openvpn):
            raise ConfigError('NCP ciphers can only be used in client or server mode')

    else:
        # checks for client-server or site-to-site bridged
        if 'local_address' in openvpn or 'remote_address' in openvpn:
            raise ConfigError('Cannot specify "local-address" or "remote-address" ' \
                              'in client/server or bridge mode')

    #
    # OpenVPN server mode - VERIFY
    #
    if openvpn['mode'] == 'server':
        if openvpn['protocol'] == 'tcp-active':
            raise ConfigError('Protocol "tcp-active" is not valid in server mode')

        if 'remote_port' in openvpn:
            raise ConfigError('Cannot specify "remote-port" in server mode')

        if 'remote_host' in openvpn:
            raise ConfigError('Cannot specify "remote-host" in server mode')

        if 'tls' in openvpn:
            if 'dh_file' not in openvpn['tls']:
                if 'key_file' in openvpn['tls'] and not checkCertHeader('-----BEGIN EC PRIVATE KEY-----', openvpn['tls']['key_file']):
                    raise ConfigError('Must specify "tls dh-file" when not using EC keys in server mode')

        tmp = dict_search('server.subnet', openvpn)
        if tmp:
            v4_subnets = len([subnet for subnet in tmp if is_ipv4(subnet)])
            v6_subnets = len([subnet for subnet in tmp if is_ipv6(subnet)])
            if v4_subnets > 1:
                raise ConfigError('Cannot specify more than 1 IPv4 server subnet')
            if v6_subnets > 1:
                raise ConfigError('Cannot specify more than 1 IPv6 server subnet')

            if v6_subnets > 0 and v4_subnets == 0:
                raise ConfigError('IPv6 server requires an IPv4 server subnet')

            for subnet in tmp:
                if is_ipv4(subnet):
                    subnet = IPv4Network(subnet)

                    if openvpn['device_type'] == 'tun' and subnet.prefixlen > 29:
                        raise ConfigError('Server subnets smaller than /29 with device type "tun" are not supported')
                    elif openvpn['device_type'] == 'tap' and subnet.prefixlen > 30:
                        raise ConfigError('Server subnets smaller than /30 with device type "tap" are not supported')

                    for client in (dict_search('client', openvpn) or []):
                        if client['ip'] and not IPv4Address(client['ip'][0]) in subnet:
                            raise ConfigError(f'Client "{client["name"]}" IP {client["ip"][0]} not in server subnet {subnet}')

        else:
            if 'is_bridge_member' not in openvpn:
                raise ConfigError('Must specify "server subnet" or add interface to bridge in server mode')


        for client in (dict_search('client', openvpn) or []):
            if len(client['ip']) > 1 or len(client['ipv6_ip']) > 1:
                raise ConfigError(f'Server client "{client["name"]}": cannot specify more than 1 IPv4 and 1 IPv6 IP')

        if dict_search('server.client_ip_pool', openvpn):
            if not (dict_search('server.client_ip_pool.start', openvpn) and dict_search('server.client_ip_pool.stop', openvpn)):
                raise ConfigError('Server client-ip-pool requires both start and stop addresses')
            else:
                v4PoolStart = IPv4Address(dict_search('server.client_ip_pool.start', openvpn))
                v4PoolStop = IPv4Address(dict_search('server.client_ip_pool.stop', openvpn))
                if v4PoolStart > v4PoolStop:
                    raise ConfigError(f'Server client-ip-pool start address {v4PoolStart} is larger than stop address {v4PoolStop}')

                v4PoolSize = int(v4PoolStop) - int(v4PoolStart)
                if v4PoolSize >= 65536:
                    raise ConfigError(f'Server client-ip-pool is too large [{v4PoolStart} -> {v4PoolStop} = {v4PoolSize}], maximum is 65536 addresses.')

                v4PoolNets = list(summarize_address_range(v4PoolStart, v4PoolStop))
                for client in (dict_search('client', openvpn) or []):
                    if client['ip']:
                        for v4PoolNet in v4PoolNets:
                            if IPv4Address(client['ip'][0]) in v4PoolNet:
                                print(f'Warning: Client "{client["name"]}" IP {client["ip"][0]} is in server IP pool, it is not reserved for this client.')

        for subnet in (dict_search('server.subnet', openvpn) or []):
            if is_ipv6(subnet):
                tmp = dict_search('client_ipv6_pool.base', openvpn)
                if tmp:
                    if not dict_search('server.client_ip_pool', openvpn):
                        raise ConfigError('IPv6 server pool requires an IPv4 server pool')

                    if int(tmp.split('/')[1]) >= 112:
                        raise ConfigError('IPv6 server pool must be larger than /112')

                    #
                    # todo - weird logic
                    #
                    v6PoolStart = IPv6Address(tmp)
                    v6PoolStop = IPv6Network((v6PoolStart, openvpn['server_ipv6_pool_prefixlen']), strict=False)[-1] # don't remove the parentheses, it's a 2-tuple
                    v6PoolSize = int(v6PoolStop) - int(v6PoolStart) if int(openvpn['server_ipv6_pool_prefixlen']) > 96 else 65536
                    if v6PoolSize < v4PoolSize:
                        raise ConfigError(f'IPv6 server pool must be at least as large as the IPv4 pool (current sizes: IPv6={v6PoolSize} IPv4={v4PoolSize})')

                    v6PoolNets = list(summarize_address_range(v6PoolStart, v6PoolStop))
                    for client in (dict_search('client', openvpn) or []):
                        if client['ipv6_ip']:
                            for v6PoolNet in v6PoolNets:
                                if IPv6Address(client['ipv6_ip'][0]) in v6PoolNet:
                                    print(f'Warning: Client "{client["name"]}" IP {client["ipv6_ip"][0]} is in server IP pool, it is not reserved for this client.')

            else:
                for route in (dict_search('server.push_route', openvpn) or []):
                    if is_ipv6(route):
                        raise ConfigError('IPv6 push-route requires an IPv6 server subnet')

            #for client in openvpn ['client']:
            #    if client['ipv6_ip']:
            #        raise ConfigError(f'Server client "{client["name"]}" IPv6 IP requires an IPv6 server subnet')
            #    if client['ipv6_push_route']:
            #        raise ConfigError(f'Server client "{client["name"]} IPv6 push-route requires an IPv6 server subnet"')
            #    if client['ipv6_subnet']:
            #        raise ConfigError(f'Server client "{client["name"]} IPv6 subnet requires an IPv6 server subnet"')

    else:
        # checks for both client and site-to-site go here
        if dict_search('server.reject_unconfigured_clients', openvpn):
            raise ConfigError('Option reject-unconfigured-clients only supported in server mode')

        if 'replace_default_route' in openvpn and 'remote_host' not in openvpn:
            raise ConfigError('Cannot set "replace-default-route" without "remote-host"')

    #
    # OpenVPN common verification section
    # not depending on any operation mode
    #

    # verify specified IP address is present on any interface on this system
    if 'local_host' in openvpn:
        if not is_addr_assigned(openvpn['local_host']):
            raise ConfigError('local-host IP address "{local_host}" not assigned' \
                              ' to any interface'.format(**openvpn))

    # TCP active
    if openvpn['protocol'] == 'tcp-active':
        if 'local_port' in openvpn:
            raise ConfigError('Cannot specify "local-port" with "tcp-active"')

        if 'remote_host' not in openvpn:
            raise ConfigError('Must specify "remote-host" with "tcp-active"')

    # shared secret and TLS
    if not ('shared_secret_key_file' in openvpn or 'tls' in openvpn):
        raise ConfigError('Must specify one of "shared-secret-key-file" and "tls"')

    if {'shared_secret_key_file', 'tls'} <= set(openvpn):
        raise ConfigError('Can only specify one of "shared-secret-key-file" and "tls"')

    if openvpn['mode'] in ['client', 'server']:
        if 'tls' not in openvpn:
            raise ConfigError('Must specify "tls" for server and client mode')

    #
    # TLS/encryption
    #
    if 'shared_secret_key_file' in openvpn:
        if dict_search('encryption.cipher', openvpn) in ['aes128gcm', 'aes192gcm', 'aes256gcm']:
            raise ConfigError('GCM encryption with shared-secret-key-file not supported')

        file = dict_search('shared_secret_key_file', openvpn)
        if file and not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', file):
            raise ConfigError(f'Specified shared-secret-key-file "{file}" is not valid')

    if 'tls' in openvpn:
        if 'ca_cert_file' not in openvpn['tls']:
            raise ConfigError('Must specify "tls ca-cert-file"')

        if not (openvpn['mode'] == 'client' and 'auth_file' in openvpn['tls']):
            if 'cert_file' not in openvpn['tls']:
                raise ConfigError('Missing "tls cert-file"')

            if 'key_file' not in openvpn['tls']:
                raise ConfigError('Missing "tls key-file"')

        if {'auth_file', 'crypt_file'} <= set(openvpn['tls']):
            raise ConfigError('TLS auth and crypt are mutually exclusive')

        file = dict_search('tls.ca_cert_file', openvpn)
        if file and not checkCertHeader('-----BEGIN CERTIFICATE-----', file):
            raise ConfigError(f'Specified ca-cert-file "{file}" is invalid')

        file = dict_search('tls.auth_file', openvpn)
        if file and not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', file):
            raise ConfigError(f'Specified auth-file "{file}" is invalid')

        file = dict_search('tls.cert_file', openvpn)
        if file and not checkCertHeader('-----BEGIN CERTIFICATE-----', file):
            raise ConfigError(f'Specified cert-file "{file}" is invalid')

        file = dict_search('tls.key_file', openvpn)
        if file and not checkCertHeader('-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', file):
            raise ConfigError(f'Specified key-file "{file}" is not valid')

        file = dict_search('tls.crypt_file', openvpn)
        if file and not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', file):
            raise ConfigError(f'Specified TLS crypt-file "{file}" is invalid')

        file = dict_search('tls.crl_file', openvpn)
        if file and not checkCertHeader('-----BEGIN X509 CRL-----', file):
            raise ConfigError(f'Specified crl-file "{file} not valid')

        file = dict_search('tls.dh_file', openvpn)
        if file and not checkCertHeader('-----BEGIN DH PARAMETERS-----', file):
            raise ConfigError(f'Specified dh-file "{file}" is not valid')

        if file and not verify_diffie_hellman_length(file, 2048):
            raise ConfigError(f'Minimum DH key-size is 2048 bits')

        tmp = dict_search('tls.role', openvpn)
        if tmp:
            if openvpn['mode'] in ['client', 'server']:
                if not dict_search('tls.auth_file', openvpn):
                    raise ConfigError('Cannot specify "tls role" in client-server mode')

            if tmp == 'active':
                if openvpn['protocol'] == 'tcp-passive':
                    raise ConfigError('Cannot specify "tcp-passive" when "tls role" is "active"')

                if dict_search('tls.dh_file', openvpn):
                    raise ConfigError('Cannot specify "tls dh-file" when "tls role" is "active"')

            elif tmp == 'passive':
                if openvpn['protocol'] == 'tcp-active':
                    raise ConfigError('Cannot specify "tcp-active" when "tls role" is "passive"')

                if not dict_search('tls.dh_file', openvpn):
                    raise ConfigError('Must specify "tls dh-file" when "tls role" is "passive"')

        file = dict_search('tls.key_file', openvpn)
        if file and checkCertHeader('-----BEGIN EC PRIVATE KEY-----', file):
            if dict_search('tls.dh_file', openvpn):
                print('Warning: using dh-file and EC keys simultaneously will ' \
                      'lead to DH ciphers being used instead of ECDH')

    if dict_search('encryption.cipher', openvpn) == 'none':
        print('Warning: "encryption none" was specified!')
        print('No encryption will be performed and data is transmitted in ' \
              'plain text over the network!')

    #
    # Auth user/pass
    #
    if (dict_search('authentication.username', openvpn) and not
        dict_search('authentication.password', openvpn)):
            raise ConfigError('Password for authentication is missing')

    if (dict_search('authentication.password', openvpn) and not
        dict_search('authentication.username', openvpn)):
            raise ConfigError('Username for authentication is missing')

    verify_vrf(openvpn)

    return None

def generate(openvpn):
    interface = openvpn['ifname']
    directory = os.path.dirname(cfg_file.format(**openvpn))

    # we can't know in advance which clients have been removed,
    # thus all client configs will be removed and re-added on demand
    ccd_dir = os.path.join(directory, 'ccd', interface)
    if os.path.isdir(ccd_dir):
        rmtree(ccd_dir, ignore_errors=True)

    if 'deleted' in openvpn or 'disable' in openvpn:
        return None

    # create client config directory on demand
    if not os.path.exists(ccd_dir):
        os.makedirs(ccd_dir, 0o755)
        chown(ccd_dir, user, group)

    # Fix file permissons for keys
    fix_permissions = []

    tmp = dict_search('shared_secret_key_file', openvpn)
    if tmp: fix_permissions.append(openvpn['shared_secret_key_file'])

    tmp = dict_search('tls.key_file', openvpn)
    if tmp: fix_permissions.append(tmp)

    # Generate User/Password authentication file
    if 'auth' in openvpn:
        with open(openvpn['auth_user_pass_file'], 'w') as f:
            f.write('{}\n{}'.format(openvpn['auth_user'], openvpn['auth_pass']))
        # also change permission on auth file
        fix_permissions.append(openvpn['auth_user_pass_file'])

    else:
        # delete old auth file if present
        if os.path.isfile(openvpn['auth_user_pass_file']):
            os.remove(openvpn['auth_user_pass_file'])

    # Generate client specific configuration
    if dict_search('server.client', openvpn):
        for client, client_config in dict_search('server.client', openvpn).items():
            client_file = os.path.join(ccd_dir, client)

            # Our client need's to know its subnet mask ...
            client_config['server_subnet'] = dict_search('server.subnet', openvpn)

            import pprint
            pprint.pprint(client_config)

            render(client_file, 'openvpn/client.conf.tmpl', client_config,
                   trim_blocks=True, user=user, group=group)

    # we need to support quoting of raw parameters from OpenVPN CLI
    # see https://phabricator.vyos.net/T1632
    render(cfg_file.format(**openvpn), 'openvpn/server.conf.tmpl', openvpn,
           trim_blocks=True, formater=lambda _: _.replace("&quot;", '"'),
           user=user, group=group)

    # Fixup file permissions
    for file in fix_permissions:
        chmod_600(file)

    return None

def apply(openvpn):
    interface = openvpn['ifname']
    call(f'systemctl stop openvpn@{interface}.service')

    # Do some cleanup when OpenVPN is disabled/deleted
    if 'deleted' in openvpn or 'disable' in openvpn:
        # cleanup old configuration files
        cleanup = []
        cleanup.append(cfg_file.format(**openvpn))
        cleanup.append(openvpn['auth_user_pass_file'])

        for file in cleanup:
            if os.path.isfile(file):
                os.unlink(file)

        if interface in interfaces():
            VTunIf(interface).remove()

        return None

    # No matching OpenVPN process running - maybe it got killed or none
    # existed - nevertheless, spawn new OpenVPN process
    call(f'systemctl start openvpn@{interface}.service')

    conf = VTunIf.get_config()
    conf['device_type'] = openvpn['device_type']

    o = VTunIf(interface, **conf)
    o.update(openvpn)

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

