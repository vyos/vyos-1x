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

from copy import deepcopy
from sys import exit
from ipaddress import ip_address,ip_network,IPv4Interface
from netifaces import interfaces
from time import sleep
from shutil import rmtree

from vyos.config import Config
from vyos.ifconfig import VTunIf
from vyos.util import call, is_bridge_member, chown, chmod_600, chmod_755
from vyos.validate import is_addr_assigned
from vyos import ConfigError
from vyos.template import render


user = 'openvpn'
group = 'openvpn'

default_config_data = {
    'address': [],
    'auth_user': '',
    'auth_pass': '',
    'auth': False,
    'bridge_member': [],
    'compress_lzo': False,
    'deleted': False,
    'description': '',
    'disable': False,
    'disable_ncp': False,
    'encryption': '',
    'hash': '',
    'intf': '',
    'ipv6_autoconf': 0,
    'ipv6_eui64_prefix': '',
    'ipv6_forwarding': 1,
    'ipv6_dup_addr_detect': 1,
    'ping_restart': '60',
    'ping_interval': '10',
    'local_address': '',
    'local_address_subnet': '',
    'local_host': '',
    'local_port': '',
    'mode': '',
    'ncp_ciphers': '',
    'options': [],
    'persistent_tunnel': False,
    'protocol': 'udp',
    'redirect_gateway': '',
    'remote_address': '',
    'remote_host': [],
    'remote_port': '',
    'client': [],
    'server_domain': '',
    'server_max_conn': '',
    'server_dns_nameserver': [],
    'server_push_route': [],
    'server_reject_unconfigured': False,
    'server_subnet': '',
    'server_topology': '',
    'shared_secret_file': '',
    'tls': False,
    'tls_auth': '',
    'tls_ca_cert': '',
    'tls_cert': '',
    'tls_crl': '',
    'tls_dh': '',
    'tls_key': '',
    'tls_crypt': '',
    'tls_role': '',
    'tls_version_min': '',
    'type': 'tun',
    'uid': user,
    'gid': group,
}


def get_config_name(intf):
    cfg_file = f'/run/openvpn/{intf}.conf'
    return cfg_file


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

def get_config():
    openvpn = deepcopy(default_config_data)
    conf = Config()

    # determine tagNode instance
    if 'VYOS_TAGNODE_VALUE' not in os.environ:
        raise ConfigError('Interface (VYOS_TAGNODE_VALUE) not specified')

    openvpn['intf'] = os.environ['VYOS_TAGNODE_VALUE']

    # Check if interface instance has been removed
    if not conf.exists('interfaces openvpn ' + openvpn['intf']):
        openvpn['deleted'] = True
        return openvpn

    # Check if we belong to any bridge interface
    for bridge in conf.list_nodes('interfaces bridge'):
        for intf in conf.list_nodes('interfaces bridge {} member interface'.format(bridge)):
            if intf == openvpn['intf']:
                openvpn['bridge_member'].append(intf)

    # set configuration level
    conf.set_level('interfaces openvpn ' + openvpn['intf'])

    # retrieve authentication options - username
    if conf.exists('authentication username'):
        openvpn['auth_user'] = conf.return_value('authentication username')
        openvpn['auth'] = True

    # retrieve authentication options - username
    if conf.exists('authentication password'):
        openvpn['auth_pass'] = conf.return_value('authentication password')
        openvpn['auth'] = True

    # retrieve interface description
    if conf.exists('description'):
        openvpn['description'] = conf.return_value('description')

    # interface device-type
    if conf.exists('device-type'):
        openvpn['type'] = conf.return_value('device-type')

    # disable interface
    if conf.exists('disable'):
        openvpn['disable'] = True

    # data encryption algorithm cipher
    if conf.exists('encryption cipher'):
        openvpn['encryption'] = conf.return_value('encryption cipher')

    # disable ncp-ciphers support
    if conf.exists('encryption disable-ncp'):
        openvpn['disable_ncp'] = True

    # data encryption algorithm ncp-list
    if conf.exists('encryption ncp-ciphers'):
        _ncp_ciphers = []
        for enc in conf.return_values('encryption ncp-ciphers'):
            if enc == 'des':
                _ncp_ciphers.append('des-cbc')
                _ncp_ciphers.append('DES-CBC')
            elif enc == '3des':
                _ncp_ciphers.append('des-ede3-cbc')
                _ncp_ciphers.append('DES-EDE3-CBC')
            elif enc == 'aes128':
                _ncp_ciphers.append('aes-128-cbc')
                _ncp_ciphers.append('AES-128-CBC')
            elif enc == 'aes128gcm':
                _ncp_ciphers.append('aes-128-gcm')
                _ncp_ciphers.append('AES-128-GCM')
            elif enc == 'aes192':
                _ncp_ciphers.append('aes-192-cbc')
                _ncp_ciphers.append('AES-192-CBC')
            elif enc == 'aes192gcm':
                _ncp_ciphers.append('aes-192-gcm')
                _ncp_ciphers.append('AES-192-GCM')
            elif enc == 'aes256':
                _ncp_ciphers.append('aes-256-cbc')
                _ncp_ciphers.append('AES-256-CBC')
            elif enc == 'aes256gcm':
                _ncp_ciphers.append('aes-256-gcm')
                _ncp_ciphers.append('AES-256-GCM')
        openvpn['ncp_ciphers'] = ':'.join(_ncp_ciphers)

    # hash algorithm
    if conf.exists('hash'):
        openvpn['hash'] = conf.return_value('hash')

    # Maximum number of keepalive packet failures
    if conf.exists('keep-alive failure-count') and conf.exists('keep-alive interval'):
        fail_count = conf.return_value('keep-alive failure-count')
        interval = conf.return_value('keep-alive interval')
        openvpn['ping_interval' ] = interval
        openvpn['ping_restart' ] = int(interval) * int(fail_count)

    # Local IP address of tunnel - even as it is a tag node - we can only work
    # on the first address
    if conf.exists('local-address'):
        openvpn['local_address'] = conf.list_nodes('local-address')[0]
        if conf.exists('local-address {} subnet-mask'.format(openvpn['local_address'])):
            openvpn['local_address_subnet'] = conf.return_value('local-address {} subnet-mask'.format(openvpn['local_address']))

    # Local IP address to accept connections
    if conf.exists('local-host'):
        openvpn['local_host'] = conf.return_value('local-host')

    # Local port number to accept connections
    if conf.exists('local-port'):
        openvpn['local_port'] = conf.return_value('local-port')

    # Enable acquisition of IPv6 address using stateless autoconfig (SLAAC)
    if conf.exists('ipv6 address autoconf'):
        openvpn['ipv6_autoconf'] = 1

    # Get prefix for IPv6 addressing based on MAC address (EUI-64)
    if conf.exists('ipv6 address eui64'):
        openvpn['ipv6_eui64_prefix'] = conf.return_value('ipv6 address eui64')

    # Disable IPv6 forwarding on this interface
    if conf.exists('ipv6 disable-forwarding'):
        openvpn['ipv6_forwarding'] = 0

    # IPv6 Duplicate Address Detection (DAD) tries
    if conf.exists('ipv6 dup-addr-detect-transmits'):
        openvpn['ipv6_dup_addr_detect'] = int(conf.return_value('ipv6 dup-addr-detect-transmits'))

    # OpenVPN operation mode
    if conf.exists('mode'):
        openvpn['mode'] = conf.return_value('mode')

    # Additional OpenVPN options
    if conf.exists('openvpn-option'):
        openvpn['options'] = conf.return_values('openvpn-option')

    # Do not close and reopen interface
    if conf.exists('persistent-tunnel'):
        openvpn['persistent_tunnel'] = True

    # Communication protocol
    if conf.exists('protocol'):
        openvpn['protocol'] = conf.return_value('protocol')

    # IP address of remote end of tunnel
    if conf.exists('remote-address'):
        openvpn['remote_address'] = conf.return_value('remote-address')

    # Remote host to connect to (dynamic if not set)
    if conf.exists('remote-host'):
        openvpn['remote_host'] = conf.return_values('remote-host')

    # Remote port number to connect to
    if conf.exists('remote-port'):
        openvpn['remote_port'] = conf.return_value('remote-port')

    # OpenVPN tunnel to be used as the default route
    # see https://openvpn.net/community-resources/reference-manual-for-openvpn-2-4/
    # redirect-gateway flags
    if conf.exists('replace-default-route'):
        openvpn['redirect_gateway'] = 'def1'

    if conf.exists('replace-default-route local'):
        openvpn['redirect_gateway'] = 'local def1'

    # Topology for clients
    if conf.exists('server topology'):
        openvpn['server_topology'] = conf.return_value('server topology')

    # Server-mode subnet (from which client IPs are allocated)
    if conf.exists('server subnet'):
        network = conf.return_value('server subnet')
        tmp = IPv4Interface(network).with_netmask
        # convert the network in format: "192.0.2.0 255.255.255.0" for later use in template
        openvpn['server_subnet'] = tmp.replace(r'/', ' ')

    # Client-specific settings
    for client in conf.list_nodes('server client'):
        # set configuration level
        conf.set_level('interfaces openvpn ' + openvpn['intf'] + ' server client ' + client)
        data = {
            'name': client,
            'disable': False,
            'ip': '',
            'push_route': [],
            'subnet': [],
            'remote_netmask': ''
        }

        # note: with "topology subnet", this is "<ip> <netmask>".
        #       with "topology p2p", this is "<ip> <our_ip>".
        if openvpn['server_topology'] == 'subnet':
            # we are only interested in the netmask portion of server_subnet
            data['remote_netmask'] = openvpn['server_subnet'].split(' ')[1]
        else:
            # we need the server subnet in format 192.0.2.0/255.255.255.0
            subnet = openvpn['server_subnet'].replace(' ', r'/')
            # get iterator over the usable hosts in the network
            tmp = ip_network(subnet).hosts()
            # OpenVPN always uses the subnets first available IP address
            data['remote_netmask'] = list(tmp)[0]

        # Option to disable client connection
        if conf.exists('disable'):
            data['disable'] = True

        # IP address of the client
        if conf.exists('ip'):
            data['ip'] = conf.return_value('ip')

        # Route to be pushed to the client
        for network in conf.return_values('push-route'):
            tmp = IPv4Interface(network).with_netmask
            data['push_route'].append(tmp.replace(r'/', ' '))

        # Subnet belonging to the client
        for network in conf.return_values('subnet'):
            tmp = IPv4Interface(network).with_netmask
            data['subnet'].append(tmp.replace(r'/', ' '))

        # Append to global client list
        openvpn['client'].append(data)

    # re-set configuration level
    conf.set_level('interfaces openvpn ' + openvpn['intf'])

    # DNS suffix to be pushed to all clients
    if conf.exists('server domain-name'):
        openvpn['server_domain'] = conf.return_value('server domain-name')

    # Number of maximum client connections
    if conf.exists('server max-connections'):
        openvpn['server_max_conn'] = conf.return_value('server max-connections')

    # Domain Name Server (DNS)
    if conf.exists('server name-server'):
        openvpn['server_dns_nameserver'] = conf.return_values('server name-server')

    # Route to be pushed to all clients
    if conf.exists('server push-route'):
        for network in conf.return_values('server push-route'):
            tmp = IPv4Interface(network).with_netmask
            openvpn['server_push_route'].append(tmp.replace(r'/', ' '))

    # Reject connections from clients that are not explicitly configured
    if conf.exists('server reject-unconfigured-clients'):
        openvpn['server_reject_unconfigured'] = True

    # File containing TLS auth static key
    if conf.exists('tls auth-file'):
        openvpn['tls_auth'] = conf.return_value('tls auth-file')
        openvpn['tls'] = True

    # File containing certificate for Certificate Authority (CA)
    if conf.exists('tls ca-cert-file'):
         openvpn['tls_ca_cert'] = conf.return_value('tls ca-cert-file')
         openvpn['tls'] = True

    # File containing certificate for this host
    if conf.exists('tls cert-file'):
         openvpn['tls_cert'] = conf.return_value('tls cert-file')
         openvpn['tls'] = True

    # File containing certificate revocation list (CRL) for this host
    if conf.exists('tls crl-file'):
         openvpn['tls_crl'] = conf.return_value('tls crl-file')
         openvpn['tls'] = True

    # File containing Diffie Hellman parameters (server only)
    if conf.exists('tls dh-file'):
         openvpn['tls_dh'] = conf.return_value('tls dh-file')
         openvpn['tls'] = True

    # File containing this host's private key
    if conf.exists('tls key-file'):
         openvpn['tls_key'] = conf.return_value('tls key-file')
         openvpn['tls'] = True

    # File containing key to encrypt control channel packets
    if conf.exists('tls crypt-file'):
         openvpn['tls_crypt'] = conf.return_value('tls crypt-file')
         openvpn['tls'] = True

    # Role in TLS negotiation
    if conf.exists('tls role'):
         openvpn['tls_role'] = conf.return_value('tls role')
         openvpn['tls'] = True

    # Minimum required TLS version
    if conf.exists('tls tls-version-min'):
         openvpn['tls_version_min'] = conf.return_value('tls tls-version-min')
         openvpn['tls'] = True

    if conf.exists('shared-secret-key-file'):
        openvpn['shared_secret_file'] = conf.return_value('shared-secret-key-file')

    if conf.exists('use-lzo-compression'):
        openvpn['compress_lzo'] = True

    # Special case when using EC certificates:
    # if key-file is EC and dh-file is unset, set tls_dh to 'none'
    if not openvpn['tls_dh'] and openvpn['tls_key'] and checkCertHeader('-----BEGIN EC PRIVATE KEY-----', openvpn['tls_key']):
        openvpn['tls_dh'] = 'none'

    return openvpn

def verify(openvpn):
    if openvpn['deleted']:
        interface = openvpn['intf']
        is_member, bridge = is_bridge_member(interface)
        if is_member:
            # can not use a f'' formatted-string here as bridge would not get
            # expanded in the print statement
            raise ConfigError('Can not delete interface "{0}" as it ' \
                              'is a member of bridge "{1}"!'.format(interface, bridge))
        return None


    if not openvpn['mode']:
        raise ConfigError('Must specify OpenVPN operation mode')

    # Checks which need to be performed on interface rmeoval
    if openvpn['deleted']:
        # OpenVPN interface can not be deleted if it's still member of a bridge
        if openvpn['bridge_member']:
            raise ConfigError('Can not delete {} as it is a member interface of bridge {}!'.format(openvpn['intf'], bridge))

    # Check if we have disabled ncp and at the same time specified ncp-ciphers
    if openvpn['disable_ncp'] and openvpn['ncp_ciphers']:
        raise ConfigError('Cannot specify both "encryption disable-ncp" and "encryption ncp-ciphers"')
    #
    # OpenVPN client mode - VERIFY
    #
    if openvpn['mode'] == 'client':
        if openvpn['local_port']:
            raise ConfigError('Cannot specify "local-port" in client mode')

        if openvpn['local_host']:
            raise ConfigError('Cannot specify "local-host" in client mode')

        if openvpn['protocol'] == 'tcp-passive':
            raise ConfigError('Protocol "tcp-passive" is not valid in client mode')

        if not openvpn['remote_host']:
            raise ConfigError('Must specify "remote-host" in client mode')

        if openvpn['tls_dh'] and openvpn['tls_dh'] != 'none':
            raise ConfigError('Cannot specify "tls dh-file" in client mode')

    #
    # OpenVPN site-to-site - VERIFY
    #
    if openvpn['mode'] == 'site-to-site':
        if openvpn['ncp_ciphers']:
            raise ConfigError('encryption ncp-ciphers cannot be specified in site-to-site mode, only server or client')

    if openvpn['mode'] == 'site-to-site' and not openvpn['bridge_member']:
        if not openvpn['local_address']:
            raise ConfigError('Must specify "local-address" or "bridge member interface"')

        for host in openvpn['remote_host']:
            if host == openvpn['remote_address']:
                raise ConfigError('"remote-address" cannot be the same as "remote-host"')

        if openvpn['type'] == 'tun':
            if not openvpn['remote_address']:
                raise ConfigError('Must specify "remote-address"')

            if openvpn['local_address'] == openvpn['remote_address']:
                raise ConfigError('"local-address" and "remote-address" cannot be the same')

            if openvpn['local_address'] == openvpn['local_host']:
                raise ConfigError('"local-address" cannot be the same as "local-host"')

    else:
        # checks for client-server or site-to-site bridged
        if openvpn['local_address'] or openvpn['remote_address']:
            raise ConfigError('Cannot specify "local-address" or "remote-address" in client-server or bridge mode')

    #
    # OpenVPN server mode - VERIFY
    #
    if openvpn['mode'] == 'server':
        if openvpn['protocol'] == 'tcp-active':
            raise ConfigError('Protocol "tcp-active" is not valid in server mode')

        if openvpn['remote_port']:
            raise ConfigError('Cannot specify "remote-port" in server mode')

        if openvpn['remote_host']:
            raise ConfigError('Cannot specify "remote-host" in server mode')

        if openvpn['protocol'] == 'tcp-passive' and len(openvpn['remote_host']) > 1:
            raise ConfigError('Cannot specify more than 1 "remote-host" with "tcp-passive"')

        if not openvpn['tls_dh'] and not checkCertHeader('-----BEGIN EC PRIVATE KEY-----', openvpn['tls_key']):
            raise ConfigError('Must specify "tls dh-file" when not using EC keys in server mode')

        if not openvpn['server_subnet']:
            if not openvpn['bridge_member']:
                raise ConfigError('Must specify "server subnet" or "bridge member interface" in server mode')

    else:
        # checks for both client and site-to-site go here
        if openvpn['server_reject_unconfigured']:
            raise ConfigError('reject-unconfigured-clients is only supported in OpenVPN server mode')

        if openvpn['server_topology']:
            raise ConfigError('The "topology" option is only valid in server mode')

        if (not openvpn['remote_host']) and openvpn['redirect_gateway']:
            raise ConfigError('Cannot set "replace-default-route" without "remote-host"')

    #
    # OpenVPN common verification section
    # not depending on any operation mode
    #

    # verify specified IP address is present on any interface on this system
    if openvpn['local_host']:
        if not is_addr_assigned(openvpn['local_host']):
            raise ConfigError('No interface on system with specified local-host IP address: {}'.format(openvpn['local_host']))

    # TCP active
    if openvpn['protocol'] == 'tcp-active':
        if openvpn['local_port']:
            raise ConfigError('Cannot specify "local-port" with "tcp-active"')

        if not openvpn['remote_host']:
            raise ConfigError('Must specify "remote-host" with "tcp-active"')

    # shared secret and TLS
    if not (openvpn['shared_secret_file'] or openvpn['tls']):
        raise ConfigError('Must specify one of "shared-secret-key-file" and "tls"')

    if openvpn['shared_secret_file'] and openvpn['tls']:
        raise ConfigError('Can only specify one of "shared-secret-key-file" and "tls"')

    if openvpn['mode'] in ['client', 'server']:
        if not openvpn['tls']:
            raise ConfigError('Must specify "tls" in client-server mode')

    #
    # TLS/encryption
    #
    if openvpn['shared_secret_file']:
        if openvpn['encryption'] in ['aes128gcm', 'aes192gcm', 'aes256gcm']:
            raise ConfigError('GCM encryption with shared-secret-key-file is not supported')

        if not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', openvpn['shared_secret_file']):
            raise ConfigError('Specified shared-secret-key-file "{}" is not valid'.format(openvpn['shared_secret_file']))

    if openvpn['tls']:
        if not openvpn['tls_ca_cert']:
            raise ConfigError('Must specify "tls ca-cert-file"')

        if not (openvpn['mode'] == 'client' and openvpn['auth']):
            if not openvpn['tls_cert']:
                raise ConfigError('Must specify "tls cert-file"')

            if not openvpn['tls_key']:
                raise ConfigError('Must specify "tls key-file"')

        if openvpn['tls_auth'] and openvpn['tls_crypt']:
            raise ConfigError('TLS auth and crypt are mutually exclusive')

        if not checkCertHeader('-----BEGIN CERTIFICATE-----', openvpn['tls_ca_cert']):
            raise ConfigError('Specified ca-cert-file "{}" is invalid'.format(openvpn['tls_ca_cert']))

        if openvpn['tls_auth']:
            if not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', openvpn['tls_auth']):
                raise ConfigError('Specified auth-file "{}" is invalid'.format(openvpn['tls_auth']))

        if openvpn['tls_cert']:
            if not checkCertHeader('-----BEGIN CERTIFICATE-----', openvpn['tls_cert']):
                raise ConfigError('Specified cert-file "{}" is invalid'.format(openvpn['tls_cert']))

        if openvpn['tls_key']:
            if not checkCertHeader('-----BEGIN (?:RSA |EC )?PRIVATE KEY-----', openvpn['tls_key']):
                raise ConfigError('Specified key-file "{}" is not valid'.format(openvpn['tls_key']))

        if openvpn['tls_crypt']:
            if not checkCertHeader('-----BEGIN OpenVPN Static key V1-----', openvpn['tls_crypt']):
                raise ConfigError('Specified TLS crypt-file "{}" is invalid'.format(openvpn['tls_crypt']))

        if openvpn['tls_crl']:
            if not checkCertHeader('-----BEGIN X509 CRL-----', openvpn['tls_crl']):
                raise ConfigError('Specified crl-file "{} not valid'.format(openvpn['tls_crl']))

        if openvpn['tls_dh'] and openvpn['tls_dh'] != 'none':
            if not checkCertHeader('-----BEGIN DH PARAMETERS-----', openvpn['tls_dh']):
                raise ConfigError('Specified dh-file "{}" is not valid'.format(openvpn['tls_dh']))

        if openvpn['tls_role']:
            if openvpn['mode'] in ['client', 'server']:
                if not openvpn['tls_auth']:
                    raise ConfigError('Cannot specify "tls role" in client-server mode')

            if openvpn['tls_role'] == 'active':
                if openvpn['protocol'] == 'tcp-passive':
                    raise ConfigError('Cannot specify "tcp-passive" when "tls role" is "active"')

                if openvpn['tls_dh'] and openvpn['tls_dh'] != 'none':
                    raise ConfigError('Cannot specify "tls dh-file" when "tls role" is "active"')

            elif openvpn['tls_role'] == 'passive':
                if openvpn['protocol'] == 'tcp-active':
                    raise ConfigError('Cannot specify "tcp-active" when "tls role" is "passive"')

                if not openvpn['tls_dh']:
                    raise ConfigError('Must specify "tls dh-file" when "tls role" is "passive"')

        if openvpn['tls_key'] and checkCertHeader('-----BEGIN EC PRIVATE KEY-----', openvpn['tls_key']):
            if openvpn['tls_dh'] and openvpn['tls_dh'] != 'none':
                print('Warning: using dh-file and EC keys simultaneously will lead to DH ciphers being used instead of ECDH')
            else:
                print('Diffie-Hellman prime file is unspecified, assuming ECDH')

    #
    # Auth user/pass
    #
    if openvpn['auth']:
        if not openvpn['auth_user']:
            raise ConfigError('Username for authentication is missing')

        if not openvpn['auth_pass']:
            raise ConfigError('Password for authentication is missing')

    #
    # Client
    #
    subnet = openvpn['server_subnet'].replace(' ', '/')
    for client in openvpn['client']:
        if client['ip'] and not ip_address(client['ip']) in ip_network(subnet):
            raise ConfigError('Client IP "{}" not in server subnet "{}'.format(client['ip'], subnet))

    return None

def generate(openvpn):
    if openvpn['deleted'] or openvpn['disable']:
        return None

    interface = openvpn['intf']
    directory = os.path.dirname(get_config_name(interface))

    # we can't know in advance which clients have been,
    # remove all client configs
    ccd_dir = os.path.join(directory, 'ccd', interface)
    if os.path.isdir(ccd_dir):
        rmtree(ccd_dir, ignore_errors=True)

    # create config directory on demand
    directories = []
    directories.append(f'{directory}/status')
    directories.append(f'{directory}/ccd/{interface}')
    for onedir in directories:
        if not os.path.exists(onedir):
            os.makedirs(onedir, 0o755)
        chown(onedir, user, group)

    # Fix file permissons for keys
    fix_permissions = []
    fix_permissions.append(openvpn['shared_secret_file'])
    fix_permissions.append(openvpn['tls_key'])

    # Generate User/Password authentication file
    user_auth_file = f'/tmp/openvpn-{interface}-pw'
    if openvpn['auth']:
        with open(user_auth_file, 'w') as f:
            f.write('{}\n{}'.format(openvpn['auth_user'], openvpn['auth_pass']))
        # also change permission on auth file
        fix_permissions.append(user_auth_file)

    else:
        # delete old auth file if present
        if os.path.isfile(user_auth_file):
            os.remove(user_auth_file)

    # Generate client specific configuration
    for client in openvpn['client']:
        client_file = os.path.join(ccd_dir, client['name'])
        render(client_file, 'openvpn/client.conf.tmpl', client)
        chown(client_file, user, group)

    # we need to support quoting of raw parameters from OpenVPN CLI
    # see https://phabricator.vyos.net/T1632
    render(get_config_name(interface), 'openvpn/server.conf.tmpl', openvpn,
           formater=lambda _: _.replace("&quot;", '"'))
    chown(get_config_name(interface), user, group)

    # Fixup file permissions
    for file in fix_permissions:
        chmod_600(file)

    return None

def apply(openvpn):
    interface = openvpn['intf']
    call(f'systemctl stop openvpn@{interface}.service')

    # Do some cleanup when OpenVPN is disabled/deleted
    if openvpn['deleted'] or openvpn['disable']:
        # cleanup old configuration file
        if os.path.isfile(get_config_name(interface)):
            os.remove(get_config_name(interface))

        # cleanup client config dir
        directory = os.path.dirname(get_config_name(interface))
        ccd_dir = os.path.join(directory, 'ccd', interface)
        if os.path.isdir(ccd_dir):
            rmtree(ccd_dir, ignore_errors=True)

        return None

    # On configuration change we need to wait for the 'old' interface to
    # vanish from the Kernel, if it is not gone, OpenVPN will report:
    # ERROR: Cannot ioctl TUNSETIFF vtun10: Device or resource busy (errno=16)
    while interface in interfaces():
        sleep(0.250) # 250ms

    # No matching OpenVPN process running - maybe it got killed or none
    # existed - nevertheless, spawn new OpenVPN process
    call(f'systemctl start openvpn@{interface}.service')

    # better late then sorry ... but we can only set interface alias after
    # OpenVPN has been launched and created the interface
    cnt = 0
    while interface not in interfaces():
        # If VPN tunnel can't be established because the peer/server isn't
        # (temporarily) available, the vtun interface never becomes registered
        # with the kernel, and the commit would hang if there is no bail out
        # condition
        cnt += 1
        if cnt == 50:
            break

        # sleep 250ms
        sleep(0.250)

    try:
        # we need to catch the exception if the interface is not up due to
        # reason stated above
        o = VTunIf(interface)
        # update interface description used e.g. within SNMP
        o.set_alias(openvpn['description'])
        # IPv6 address autoconfiguration
        o.set_ipv6_autoconf(openvpn['ipv6_autoconf'])
        # IPv6 EUI-based address
        o.set_ipv6_eui64_address(openvpn['ipv6_eui64_prefix'])
        # IPv6 forwarding
        o.set_ipv6_forwarding(openvpn['ipv6_forwarding'])
        # IPv6 Duplicate Address Detection (DAD) tries
        o.set_ipv6_dad_messages(openvpn['ipv6_dup_addr_detect'])

    except:
        pass

    # TAP interface needs to be brought up explicitly
    if openvpn['type'] == 'tap':
        if not openvpn['disable']:
            VTunIf(interface).set_admin_state('up')

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
