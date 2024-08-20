#!/usr/bin/env python3
#
# Copyright (C) 2019-2024 VyOS maintainers and contributors
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

from cryptography.hazmat.primitives.asymmetric import ec
from glob import glob
from sys import exit
from ipaddress import IPv4Address
from ipaddress import IPv4Network
from ipaddress import IPv6Address
from ipaddress import IPv6Network
from ipaddress import summarize_address_range
from secrets import SystemRandom
from shutil import rmtree

from vyos.base import DeprecationWarning
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configverify import verify_vrf
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_bond_bridge_member
from vyos.ifconfig import VTunIf
from vyos.pki import load_dh_parameters
from vyos.pki import load_private_key
from vyos.pki import sort_ca_chain
from vyos.pki import verify_ca_chain
from vyos.pki import wrap_certificate
from vyos.pki import wrap_crl
from vyos.pki import wrap_dh_parameters
from vyos.pki import wrap_openvpn_key
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.list import is_list_equal
from vyos.utils.file import makedir
from vyos.utils.file import read_file
from vyos.utils.file import write_file
from vyos.utils.kernel import check_kmod
from vyos.utils.kernel import unload_kmod
from vyos.utils.process import call
from vyos.utils.permission import chown
from vyos.utils.process import cmd
from vyos.utils.network import is_addr_assigned
from vyos.utils.network import interface_exists

from vyos import ConfigError
from vyos import airbag
airbag.enable()

user = 'openvpn'
group = 'openvpn'

cfg_dir = '/run/openvpn'
cfg_file = '/run/openvpn/{ifname}.conf'
otp_path = '/config/auth/openvpn'
otp_file = '/config/auth/openvpn/{ifname}-otp-secrets'
secret_chars = list('ABCDEFGHIJKLMNOPQRSTUVWXYZ234567')
service_file = '/run/systemd/system/openvpn@{ifname}.service.d/20-override.conf'

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

    ifname, openvpn = get_interface_dict(conf, base, with_pki=True)
    openvpn['auth_user_pass_file'] = '/run/openvpn/{ifname}.pw'.format(**openvpn)

    if 'deleted' in openvpn:
        return openvpn

    if is_node_changed(conf, base + [ifname, 'openvpn-option']):
        openvpn.update({'restart_required': {}})
    if is_node_changed(conf, base + [ifname, 'enable-dco']):
        openvpn.update({'restart_required': {}})

    # We have to get the dict using 'get_config_dict' instead of 'get_interface_dict'
    # as 'get_interface_dict' merges the defaults in, so we can not check for defaults in there.
    tmp = conf.get_config_dict(base + [openvpn['ifname']], get_first_key=True)

    # We have to cleanup the config dict, as default values could enable features
    # which are not explicitly enabled on the CLI. Example: server mfa totp
    # originate comes with defaults, which will enable the
    # totp plugin, even when not set via CLI so we
    # need to check this first and drop those keys
    if dict_search('server.mfa.totp', tmp) == None:
        del openvpn['server']['mfa']

    # OpenVPN Data-Channel-Offload (DCO) is a Kernel module. If loaded it applies to all
    # OpenVPN interfaces. Check if DCO is used by any other interface instance.
    tmp = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    for interface, interface_config in tmp.items():
        # If one interface has DCO configured, enable it. No need to further check
        # all other OpenVPN interfaces. We must use a dedicated key to indicate
        # the Kernel module must be loaded or not. The per interface "offload.dco"
        # key is required per OpenVPN interface instance.
        if dict_search('offload.dco', interface_config) != None:
            openvpn['module_load_dco'] = {}
            break

    # Calculate the protocol modifier. This is concatenated to the protocol string to direct
    # OpenVPN to use a specific IP protocol version. If unspecified, the kernel decides which
    # type of socket to open. In server mode, an additional "ipv6-dual-stack" option forces
    # binding the socket in IPv6 mode, which can also receive IPv4 traffic (when using the
    # default "ipv6" mode, we specify "bind ipv6only" to disable kernel dual-stack behaviors).
    if openvpn['ip_version'] == 'ipv4':
        openvpn['protocol_modifier'] = '4'
    elif openvpn['ip_version'] in ['ipv6', 'dual-stack']:
        openvpn['protocol_modifier']  = '6'
    else:
        openvpn['protocol_modifier'] = ''

    return openvpn

def is_ec_private_key(pki, cert_name):
    if not pki or 'certificate' not in pki:
        return False
    if cert_name not in pki['certificate']:
        return False

    pki_cert = pki['certificate'][cert_name]
    if 'private' not in pki_cert or 'key' not in pki_cert['private']:
        return False

    key = load_private_key(pki_cert['private']['key'])
    return isinstance(key, ec.EllipticCurvePrivateKey)

def verify_pki(openvpn):
    pki = openvpn['pki']
    interface = openvpn['ifname']
    mode = openvpn['mode']
    shared_secret_key = dict_search_args(openvpn, 'shared_secret_key')
    tls = dict_search_args(openvpn, 'tls')

    if not bool(shared_secret_key) ^ bool(tls): #  xor check if only one is set
        raise ConfigError('Must specify only one of "shared-secret-key" and "tls"')

    if mode in ['server', 'client'] and not tls:
        raise ConfigError('Must specify "tls" for server and client modes')

    if not pki:
        raise ConfigError('PKI is not configured')

    if shared_secret_key:
        if not dict_search_args(pki, 'openvpn', 'shared_secret'):
            raise ConfigError('There are no openvpn shared-secrets in PKI configuration')

        if shared_secret_key not in pki['openvpn']['shared_secret']:
            raise ConfigError(f'Invalid shared-secret on openvpn interface {interface}')

        # If PSK settings are correct, warn about its deprecation
        DeprecationWarning('OpenVPN shared-secret support will be removed in future '\
                           'VyOS versions. Please migrate your site-to-site tunnels to '\
                           'TLS. You can use self-signed certificates with peer fingerprint '\
                           'verification, consult the documentation for details.')

    if tls:
        if mode == 'site-to-site':
            # XXX: site-to-site with PSKs is the only mode that can work without TLS,
            # so 'tls role' is not mandatory for it,
            # but we need to check that if it uses peer certificate fingerprints rather than PSKs,
            # then the TLS role is set
            if ('shared_secret_key' not in tls) and ('role' not in tls):
                raise ConfigError('"tls role" is required for site-to-site OpenVPN with TLS')

        if (mode in ['server', 'client']) and ('ca_certificate' not in tls):
            raise ConfigError(f'Must specify "tls ca-certificate" on openvpn interface {interface},\
              it is required in server and client modes')
        else:
            if ('ca_certificate' not in tls) and ('peer_fingerprint' not in tls):
                raise ConfigError('Either "tls ca-certificate" or "tls peer-fingerprint" is required\
                  on openvpn interface {interface} in site-to-site mode')

        if 'ca_certificate' in tls:
            for ca_name in tls['ca_certificate']:
                if ca_name not in pki['ca']:
                    raise ConfigError(f'Invalid CA certificate on openvpn interface {interface}')

            if len(tls['ca_certificate']) > 1:
                sorted_chain = sort_ca_chain(tls['ca_certificate'], pki['ca'])
                if not verify_ca_chain(sorted_chain, pki['ca']):
                    raise ConfigError(f'CA certificates are not a valid chain')

        if mode != 'client' and 'auth_key' not in tls:
            if 'certificate' not in tls:
                raise ConfigError(f'Missing "tls certificate" on openvpn interface {interface}')

        if 'certificate' in tls:
            if tls['certificate'] not in pki['certificate']:
                raise ConfigError(f'Invalid certificate on openvpn interface {interface}')

            if dict_search_args(pki, 'certificate', tls['certificate'], 'private', 'password_protected') is not None:
                raise ConfigError(f'Cannot use encrypted private key on openvpn interface {interface}')

        if 'dh_params' in tls:
            if 'dh' not in pki:
                raise ConfigError(f'pki dh is not configured')
            proposed_dh = tls['dh_params']
            if proposed_dh not in pki['dh'].keys():
                raise ConfigError(f"pki dh '{proposed_dh}' is not configured")

            pki_dh = pki['dh'][tls['dh_params']]
            dh_params = load_dh_parameters(pki_dh['parameters'])
            dh_numbers = dh_params.parameter_numbers()
            dh_bits = dh_numbers.p.bit_length()

            if dh_bits < 2048:
                raise ConfigError(f'Minimum DH key-size is 2048 bits')


        if 'auth_key' in tls or 'crypt_key' in tls:
            if not dict_search_args(pki, 'openvpn', 'shared_secret'):
                raise ConfigError('There are no openvpn shared-secrets in PKI configuration')

        if 'auth_key' in tls:
            if tls['auth_key'] not in pki['openvpn']['shared_secret']:
                raise ConfigError(f'Invalid auth-key on openvpn interface {interface}')

        if 'crypt_key' in tls:
            if tls['crypt_key'] not in pki['openvpn']['shared_secret']:
                raise ConfigError(f'Invalid crypt-key on openvpn interface {interface}')

def verify(openvpn):
    if 'deleted' in openvpn:
        verify_bridge_delete(openvpn)
        return None

    if 'mode' not in openvpn:
        raise ConfigError('Must specify OpenVPN operation mode!')

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

        if 'ip_version' in openvpn and openvpn['ip_version'] == 'dual-stack':
            raise ConfigError('"ip-version dual-stack" is not supported in client mode')

        if dict_search('tls.dh_params', openvpn):
            raise ConfigError('Cannot specify "tls dh-params" in client mode')

    #
    # OpenVPN site-to-site - VERIFY
    #
    elif openvpn['mode'] == 'site-to-site':
        if 'ip_version' in openvpn and openvpn['ip_version'] == 'dual-stack':
            raise ConfigError('"ip-version dual-stack" is not supported in site-to-site mode')

        if 'local_address' not in openvpn and 'is_bridge_member' not in openvpn:
            raise ConfigError('Must specify "local-address" or add interface to bridge')

        if 'local_address' in openvpn:
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

            if is_list_equal(v4loAddr, v4remAddr) or is_list_equal(v6loAddr, v6remAddr):
                raise ConfigError('"local-address" and "remote-address" cannot be the same')

            if dict_search('local_host', openvpn) in dict_search('local_address', openvpn):
                raise ConfigError('"local-address" cannot be the same as "local-host"')

            if dict_search('remote_host', openvpn) in dict_search('remote_address', openvpn):
                raise ConfigError('"remote-address" and "remote-host" can not be the same')

        if openvpn['device_type'] == 'tap' and 'local_address' in openvpn:
            # we can only have one local_address, this is ensured above
            v4addr = None
            for laddr in openvpn['local_address']:
                if is_ipv4(laddr):
                    v4addr = laddr
                    break

            if v4addr in openvpn['local_address'] and 'subnet_mask' not in openvpn['local_address'][v4addr]:
                raise ConfigError('Must specify IPv4 "subnet-mask" for local-address')

        if dict_search('encryption.data_ciphers', openvpn):
            raise ConfigError('Cipher negotiation can only be used in client or server mode')

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

        if dict_search('authentication.username', openvpn) or dict_search('authentication.password', openvpn):
            raise ConfigError('Cannot specify "authentication" in server mode')

        if 'remote_port' in openvpn:
            raise ConfigError('Cannot specify "remote-port" in server mode')

        if 'remote_host' in openvpn:
            raise ConfigError('Cannot specify "remote-host" in server mode')

        tmp = dict_search('server.subnet', openvpn)
        if tmp:
            v4_subnets = len([subnet for subnet in tmp if is_ipv4(subnet)])
            v6_subnets = len([subnet for subnet in tmp if is_ipv6(subnet)])
            if v4_subnets > 1:
                raise ConfigError('Cannot specify more than 1 IPv4 server subnet')
            if v6_subnets > 1:
                raise ConfigError('Cannot specify more than 1 IPv6 server subnet')

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

        if hasattr(dict_search('server.client', openvpn), '__iter__'):
            for client_k, client_v in dict_search('server.client', openvpn).items():
                if (client_v.get('ip') and len(client_v['ip']) > 1) or (client_v.get('ipv6_ip') and len(client_v['ipv6_ip']) > 1):
                    raise ConfigError(f'Server client "{client_k}": cannot specify more than 1 IPv4 and 1 IPv6 IP')

        if dict_search('server.bridge', openvpn):
            # check if server bridge is a tap interfaces
            if not openvpn['device_type'] == 'tap' and dict_search('server.bridge', openvpn):
               raise ConfigError('Must specify "device-type tap" with server bridge mode')
            elif not (dict_search('server.bridge.start', openvpn) and dict_search('server.bridge.stop', openvpn)):
                raise ConfigError('Server bridge requires both start and stop addresses')
            else:
                v4PoolStart = IPv4Address(dict_search('server.bridge.start', openvpn))
                v4PoolStop = IPv4Address(dict_search('server.bridge.stop', openvpn))
                if v4PoolStart > v4PoolStop:
                    raise ConfigError(f'Server bridge start address {v4PoolStart} is larger than stop address {v4PoolStop}')

                v4PoolSize = int(v4PoolStop) - int(v4PoolStart)
                if v4PoolSize >= 65536:
                    raise ConfigError(f'Server bridge is too large [{v4PoolStart} -> {v4PoolStop} = {v4PoolSize}], maximum is 65536 addresses.')

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
            # configuring a client_ip_pool will set 'server ... nopool' which is currently incompatible with 'server-ipv6' (probably to be fixed upstream)
            for subnet in (dict_search('server.subnet', openvpn) or []):
                if is_ipv6(subnet):
                    raise ConfigError(f'Setting client-ip-pool is incompatible having an IPv6 server subnet.')

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

        if 'topology' in openvpn['server']:
            if openvpn['server']['topology'] == 'net30':
                DeprecationWarning('Topology net30 is deprecated '\
                                   'and will be removed in future VyOS versions. '\
                                   'Switch to "subnet" or "p2p"'
                )

        # add mfa users to the file the mfa plugin uses
        if dict_search('server.mfa.totp', openvpn):
            user_data = ''
            if not os.path.isfile(otp_file.format(**openvpn)):
                write_file(otp_file.format(**openvpn), user_data,
                           user=user, group=group, mode=0o644)

            ovpn_users = read_file(otp_file.format(**openvpn))
            for client in (dict_search('server.client', openvpn) or []):
                exists = None
                for ovpn_user in ovpn_users.split('\n'):
                    if re.search('^' + client + ' ', ovpn_user):
                        user_data += f'{ovpn_user}\n'
                        exists = 'true'

                if not exists:
                    random = SystemRandom()
                    totp_secret = ''.join(random.choice(secret_chars) for _ in range(16))
                    user_data += f'{client} otp totp:sha1:base32:{totp_secret}::xxx *\n'

            write_file(otp_file.format(**openvpn), user_data,
                           user=user, group=group, mode=0o644)

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

    # verify that local_host/remote_host match with any ip_version override
    # specified (if a dns name is specified for remote_host, no attempt is made
    # to verify that record resolves to an address of the configured family)
    if 'local_host' in openvpn:
        if openvpn['ip_version'] == 'ipv4' and is_ipv6(openvpn['local_host']):
            raise ConfigError('Cannot use an IPv6 "local-host" with "ip-version ipv4"')
        elif openvpn['ip_version'] == 'ipv6' and is_ipv4(openvpn['local_host']):
            raise ConfigError('Cannot use an IPv4 "local-host" with "ip-version ipv6"')
        elif openvpn['ip_version'] == 'dual-stack':
            raise ConfigError('Cannot use "local-host" with "ip-version dual-stack". "dual-stack" is only supported when OpenVPN binds to all available interfaces.')

    if 'remote_host' in openvpn:
        remote_hosts = dict_search('remote_host', openvpn)
        for remote_host in remote_hosts:
            if openvpn['ip_version'] == 'ipv4' and is_ipv6(remote_host):
                raise ConfigError('Cannot use an IPv6 "remote-host" with "ip-version ipv4"')
            elif openvpn['ip_version'] == 'ipv6' and is_ipv4(remote_host):
                raise ConfigError('Cannot use an IPv4 "remote-host" with "ip-version ipv6"')

    # verify specified IP address is present on any interface on this system
    if 'local_host' in openvpn:
        if not is_addr_assigned(openvpn['local_host']):
            print('local-host IP address "{local_host}" not assigned' \
                  ' to any interface'.format(**openvpn))

    # TCP active
    if openvpn['protocol'] == 'tcp-active':
        if 'local_port' in openvpn:
            raise ConfigError('Cannot specify "local-port" with "tcp-active"')

        if 'remote_host' not in openvpn:
            raise ConfigError('Must specify "remote-host" with "tcp-active"')

    #
    # TLS/encryption
    #
    if 'shared_secret_key' in openvpn:
        if dict_search('encryption.cipher', openvpn) in ['aes128gcm', 'aes192gcm', 'aes256gcm']:
            raise ConfigError('GCM encryption with shared-secret-key not supported')

    if 'tls' in openvpn:
        if {'auth_key', 'crypt_key'} <= set(openvpn['tls']):
            raise ConfigError('TLS auth and crypt keys are mutually exclusive')

        tmp = dict_search('tls.role', openvpn)
        if tmp:
            if openvpn['mode'] in ['client', 'server']:
                if not dict_search('tls.auth_key', openvpn):
                    raise ConfigError('Cannot specify "tls role" in client-server mode')

            if tmp == 'active':
                if openvpn['protocol'] == 'tcp-passive':
                    raise ConfigError('Cannot specify "tcp-passive" when "tls role" is "active"')

                if dict_search('tls.dh_params', openvpn):
                    raise ConfigError('Cannot specify "tls dh-params" when "tls role" is "active"')

            elif tmp == 'passive':
                if openvpn['protocol'] == 'tcp-active':
                    raise ConfigError('Cannot specify "tcp-active" when "tls role" is "passive"')

        if 'certificate' in openvpn['tls'] and is_ec_private_key(openvpn['pki'], openvpn['tls']['certificate']):
            if 'dh_params' in openvpn['tls']:
                print('Warning: using dh-params and EC keys simultaneously will ' \
                      'lead to DH ciphers being used instead of ECDH')

        if dict_search('encryption.cipher', openvpn):
            raise ConfigError('"encryption cipher" option is deprecated for TLS mode. '
                              'Use "encryption data-ciphers" instead')

    if dict_search('encryption.cipher', openvpn) == 'none':
        print('Warning: "encryption none" was specified!')
        print('No encryption will be performed and data is transmitted in ' \
              'plain text over the network!')

    verify_pki(openvpn)

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
    verify_bond_bridge_member(openvpn)
    verify_mirror_redirect(openvpn)

    return None

def generate_pki_files(openvpn):
    pki = openvpn['pki']
    if not pki:
        return None

    interface = openvpn['ifname']
    shared_secret_key = dict_search_args(openvpn, 'shared_secret_key')
    tls = dict_search_args(openvpn, 'tls')

    if shared_secret_key:
        pki_key = pki['openvpn']['shared_secret'][shared_secret_key]
        key_path = os.path.join(cfg_dir, f'{interface}_shared.key')
        write_file(key_path, wrap_openvpn_key(pki_key['key']),
                   user=user, group=group)

    if tls:
        if 'ca_certificate' in tls:
            cert_path = os.path.join(cfg_dir, f'{interface}_ca.pem')
            crl_path = os.path.join(cfg_dir, f'{interface}_crl.pem')

            if os.path.exists(cert_path):
                os.unlink(cert_path)

            if os.path.exists(crl_path):
                os.unlink(crl_path)

            for cert_name in sort_ca_chain(tls['ca_certificate'], pki['ca']):
                pki_ca = pki['ca'][cert_name]

                if 'certificate' in pki_ca:
                    write_file(cert_path, wrap_certificate(pki_ca['certificate']) + "\n",
                               user=user, group=group, mode=0o600, append=True)

                if 'crl' in pki_ca:
                    for crl in pki_ca['crl']:
                        write_file(crl_path, wrap_crl(crl) + "\n", user=user, group=group,
                                   mode=0o600, append=True)

                    openvpn['tls']['crl'] = True

        if 'certificate' in tls:
            cert_name = tls['certificate']
            pki_cert = pki['certificate'][cert_name]

            if 'certificate' in pki_cert:
                cert_path = os.path.join(cfg_dir, f'{interface}_cert.pem')
                write_file(cert_path, wrap_certificate(pki_cert['certificate']),
                           user=user, group=group, mode=0o600)

            if 'private' in pki_cert and 'key' in pki_cert['private']:
                key_path = os.path.join(cfg_dir, f'{interface}_cert.key')
                write_file(key_path, wrap_private_key(pki_cert['private']['key']),
                           user=user, group=group, mode=0o600)

                openvpn['tls']['private_key'] = True

        if 'dh_params' in tls:
            dh_name = tls['dh_params']
            pki_dh = pki['dh'][dh_name]

            if 'parameters' in pki_dh:
                dh_path = os.path.join(cfg_dir, f'{interface}_dh.pem')
                write_file(dh_path, wrap_dh_parameters(pki_dh['parameters']),
                           user=user, group=group, mode=0o600)

        if 'auth_key' in tls:
            key_name = tls['auth_key']
            pki_key = pki['openvpn']['shared_secret'][key_name]

            if 'key' in pki_key:
                key_path = os.path.join(cfg_dir, f'{interface}_auth.key')
                write_file(key_path, wrap_openvpn_key(pki_key['key']),
                           user=user, group=group, mode=0o600)

        if 'crypt_key' in tls:
            key_name = tls['crypt_key']
            pki_key = pki['openvpn']['shared_secret'][key_name]

            if 'key' in pki_key:
                key_path = os.path.join(cfg_dir, f'{interface}_crypt.key')
                write_file(key_path, wrap_openvpn_key(pki_key['key']),
                           user=user, group=group, mode=0o600)


def generate(openvpn):
    if 'deleted' in openvpn:
        # remove totp secrets file if totp is not configured
        if os.path.isfile(otp_file.format(**openvpn)):
            os.remove(otp_file.format(**openvpn))
        return None

    if 'disable' in openvpn:
        return None

    interface = openvpn['ifname']
    directory = os.path.dirname(cfg_file.format(**openvpn))
    openvpn['plugin_dir'] = '/usr/lib/openvpn'

    # create base config directory on demand
    makedir(directory, user, group)
    # enforce proper permissions on /run/openvpn
    chown(directory, user, group)

    # we can't know in advance which clients have been removed,
    # thus all client configs will be removed and re-added on demand
    ccd_dir = os.path.join(directory, 'ccd', interface)
    if os.path.isdir(ccd_dir):
        rmtree(ccd_dir, ignore_errors=True)

    # Remove systemd directories with overrides
    service_dir = os.path.dirname(service_file.format(**openvpn))
    if os.path.isdir(service_dir):
        rmtree(service_dir, ignore_errors=True)

    # create client config directory on demand
    makedir(ccd_dir, user, group)

    # Fix file permissons for keys
    generate_pki_files(openvpn)

    # Generate User/Password authentication file
    if 'authentication' in openvpn:
        render(openvpn['auth_user_pass_file'], 'openvpn/auth.pw.j2', openvpn,
               user=user, group=group, permission=0o600)
    else:
        # delete old auth file if present
        if os.path.isfile(openvpn['auth_user_pass_file']):
            os.remove(openvpn['auth_user_pass_file'])

    # Generate client specific configuration
    server_client = dict_search_args(openvpn, 'server', 'client')
    if server_client:
        for client, client_config in server_client.items():
            client_file = os.path.join(ccd_dir, client)

            # Our client need's to know its subnet mask ...
            client_config['server_subnet'] = dict_search('server.subnet', openvpn)

            render(client_file, 'openvpn/client.conf.j2', client_config,
                   user=user, group=group)

    # we need to support quoting of raw parameters from OpenVPN CLI
    # see https://vyos.dev/T1632
    render(cfg_file.format(**openvpn), 'openvpn/server.conf.j2', openvpn,
           formater=lambda _: _.replace("&quot;", '"'), user=user, group=group)

    # Render 20-override.conf for OpenVPN service
    render(service_file.format(**openvpn), 'openvpn/service-override.conf.j2', openvpn,
           formater=lambda _: _.replace("&quot;", '"'), user=user, group=group)
    # Reload systemd services config to apply an override
    call(f'systemctl daemon-reload')

    return None

def apply(openvpn):
    interface = openvpn['ifname']

    # Do some cleanup when OpenVPN is disabled/deleted
    if 'deleted' in openvpn or 'disable' in openvpn:
        call(f'systemctl stop openvpn@{interface}.service')
        for cleanup_file in glob(f'/run/openvpn/{interface}.*'):
            if os.path.isfile(cleanup_file):
                os.unlink(cleanup_file)

        if interface_exists(interface):
            VTunIf(interface).remove()

    # dynamically load/unload DCO Kernel extension if requested
    dco_module = 'ovpn_dco_v2'
    if 'module_load_dco' in openvpn:
        check_kmod(dco_module)
    else:
        unload_kmod(dco_module)

    # Now bail out early if interface is disabled or got deleted
    if 'deleted' in openvpn or 'disable' in openvpn:
        return None

    # verify specified IP address is present on any interface on this system
    # Allow to bind service to nonlocal address, if it virtaual-vrrp address
    # or if address will be assign later
    if 'local_host' in openvpn:
        if not is_addr_assigned(openvpn['local_host']):
            cmd('sysctl -w net.ipv4.ip_nonlocal_bind=1')

    # No matching OpenVPN process running - maybe it got killed or none
    # existed - nevertheless, spawn new OpenVPN process
    action = 'reload-or-restart'
    if 'restart_required' in openvpn:
        action = 'restart'
    call(f'systemctl {action} openvpn@{interface}.service')

    o = VTunIf(**openvpn)
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
