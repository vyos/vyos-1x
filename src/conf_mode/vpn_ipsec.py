#!/usr/bin/env python3
#
# Copyright (C) 2021-2024 VyOS maintainers and contributors
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

import ipaddress
import os
import re
import jmespath

from sys import exit
from time import sleep

from vyos.base import Warning
from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_interface_exists
from vyos.configverify import dynamic_interface_pattern
from vyos.defaults import directories
from vyos.ifconfig import Interface
from vyos.pki import encode_public_key
from vyos.pki import load_private_key
from vyos.pki import wrap_certificate
from vyos.pki import wrap_crl
from vyos.pki import wrap_public_key
from vyos.pki import wrap_private_key
from vyos.template import ip_from_cidr
from vyos.template import is_ipv4
from vyos.template import is_ipv6
from vyos.template import render
from vyos.utils.network import is_ipv6_link_local
from vyos.utils.network import interface_exists
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag
airbag.enable()

dhcp_wait_attempts = 2
dhcp_wait_sleep = 1

swanctl_dir        = '/etc/swanctl'
charon_conf        = '/etc/strongswan.d/charon.conf'
charon_dhcp_conf   = '/etc/strongswan.d/charon/dhcp.conf'
charon_radius_conf = '/etc/strongswan.d/charon/eap-radius.conf'
interface_conf     = '/etc/strongswan.d/interfaces_use.conf'
swanctl_conf       = f'{swanctl_dir}/swanctl.conf'

default_install_routes = 'yes'

vici_socket = '/var/run/charon.vici'

CERT_PATH   = f'{swanctl_dir}/x509/'
PUBKEY_PATH = f'{swanctl_dir}/pubkey/'
KEY_PATH    = f'{swanctl_dir}/private/'
CA_PATH     = f'{swanctl_dir}/x509ca/'
CRL_PATH    = f'{swanctl_dir}/x509crl/'

DHCP_HOOK_IFLIST = '/tmp/ipsec_dhcp_interfaces'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'ipsec']
    l2tp_base = ['vpn', 'l2tp', 'remote-access', 'ipsec-settings']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipsec = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 no_tag_node_value_mangle=True,
                                 get_first_key=True,
                                 with_recursive_defaults=True,
                                 with_pki=True)

    ipsec['dhcp_interfaces'] = set()
    ipsec['dhcp_no_address'] = {}
    ipsec['install_routes'] = 'no' if conf.exists(base + ["options", "disable-route-autoinstall"]) else default_install_routes
    ipsec['interface_change'] = leaf_node_changed(conf, base + ['interface'])
    ipsec['nhrp_exists'] = conf.exists(['protocols', 'nhrp', 'tunnel'])

    if ipsec['nhrp_exists']:
        set_dependents('nhrp', conf)

    tmp = conf.get_config_dict(l2tp_base, key_mangling=('-', '_'),
                               no_tag_node_value_mangle=True,
                               get_first_key=True)
    if tmp:
        ipsec['l2tp'] = conf.merge_defaults(tmp, recursive=True)
        ipsec['l2tp_outside_address'] = conf.return_value(['vpn', 'l2tp', 'remote-access', 'outside-address'])
        ipsec['l2tp_ike_default'] = 'aes256-sha1-modp1024,3des-sha1-modp1024'
        ipsec['l2tp_esp_default'] = 'aes256-sha1,3des-sha1'

    return ipsec

def get_dhcp_address(iface):
    addresses = Interface(iface).get_addr()
    if not addresses:
        return None
    for address in addresses:
        if not is_ipv6_link_local(address):
            return ip_from_cidr(address)
    return None

def verify_pki_x509(pki, x509_conf):
    if not pki or 'ca' not in pki or 'certificate' not in pki:
        raise ConfigError(f'PKI is not configured')

    cert_name = x509_conf['certificate']

    for ca_cert_name in x509_conf['ca_certificate']:
        if not dict_search_args(pki, 'ca', ca_cert_name, 'certificate'):
            raise ConfigError(f'Missing CA certificate on specified PKI CA certificate "{ca_cert_name}"')

    if not dict_search_args(pki, 'certificate', cert_name, 'certificate'):
        raise ConfigError(f'Missing certificate on specified PKI certificate "{cert_name}"')

    if not dict_search_args(pki, 'certificate', cert_name, 'private', 'key'):
        raise ConfigError(f'Missing private key on specified PKI certificate "{cert_name}"')

    return True

def verify_pki_rsa(pki, rsa_conf):
    if not pki or 'key_pair' not in pki:
        raise ConfigError(f'PKI is not configured')

    local_key = rsa_conf['local_key']
    remote_key = rsa_conf['remote_key']

    if not dict_search_args(pki, 'key_pair', local_key, 'private', 'key'):
        raise ConfigError(f'Missing private key on specified local-key "{local_key}"')

    if not dict_search_args(pki, 'key_pair', remote_key, 'public', 'key'):
        raise ConfigError(f'Missing public key on specified remote-key "{remote_key}"')

    return True

def verify(ipsec):
    if not ipsec:
        return None

    if 'authentication' in ipsec:
        if 'psk' in ipsec['authentication']:
            for psk, psk_config in ipsec['authentication']['psk'].items():
                if 'id' not in psk_config or 'secret' not in psk_config:
                    raise ConfigError(f'Authentication psk "{psk}" missing "id" or "secret"')

    if 'interface' in ipsec:
        tmp = re.compile(dynamic_interface_pattern)
        for interface in ipsec['interface']:
            # exclude check interface for dynamic interfaces
            if tmp.match(interface):
                verify_interface_exists(interface, warning_only=True)
            else:
                verify_interface_exists(interface)

    if 'l2tp' in ipsec:
        if 'esp_group' in ipsec['l2tp']:
            if 'esp_group' not in ipsec or ipsec['l2tp']['esp_group'] not in ipsec['esp_group']:
                raise ConfigError(f"Invalid esp-group on L2TP remote-access config")

        if 'ike_group' in ipsec['l2tp']:
            if 'ike_group' not in ipsec or ipsec['l2tp']['ike_group'] not in ipsec['ike_group']:
                raise ConfigError(f"Invalid ike-group on L2TP remote-access config")

        if 'authentication' not in ipsec['l2tp']:
            raise ConfigError(f'Missing authentication settings on L2TP remote-access config')

        if 'mode' not in ipsec['l2tp']['authentication']:
            raise ConfigError(f'Missing authentication mode on L2TP remote-access config')

        if not ipsec['l2tp_outside_address']:
            raise ConfigError(f'Missing outside-address on L2TP remote-access config')

        if ipsec['l2tp']['authentication']['mode'] == 'pre-shared-secret':
            if 'pre_shared_secret' not in ipsec['l2tp']['authentication']:
                raise ConfigError(f'Missing pre shared secret on L2TP remote-access config')

        if ipsec['l2tp']['authentication']['mode'] == 'x509':
            if 'x509' not in ipsec['l2tp']['authentication']:
                raise ConfigError(f'Missing x509 settings on L2TP remote-access config')

            x509 = ipsec['l2tp']['authentication']['x509']

            if 'ca_certificate' not in x509 or 'certificate' not in x509:
                raise ConfigError(f'Missing x509 certificates on L2TP remote-access config')

            verify_pki_x509(ipsec['pki'], x509)

    if 'profile' in ipsec:
        for profile, profile_conf in ipsec['profile'].items():
            if 'esp_group' in profile_conf:
                if 'esp_group' not in ipsec or profile_conf['esp_group'] not in ipsec['esp_group']:
                    raise ConfigError(f"Invalid esp-group on {profile} profile")
            else:
                raise ConfigError(f"Missing esp-group on {profile} profile")

            if 'ike_group' in profile_conf:
                if 'ike_group' not in ipsec or profile_conf['ike_group'] not in ipsec['ike_group']:
                    raise ConfigError(f"Invalid ike-group on {profile} profile")
            else:
                raise ConfigError(f"Missing ike-group on {profile} profile")

            if 'authentication' not in profile_conf:
                raise ConfigError(f"Missing authentication on {profile} profile")

    if 'remote_access' in ipsec:
        if 'connection' in ipsec['remote_access']:
            for name, ra_conf in ipsec['remote_access']['connection'].items():
                if 'local_address' not in ra_conf and 'dhcp_interface' not in ra_conf:
                    raise ConfigError(f"Missing local-address or dhcp-interface on remote-access connection {name}")

                if 'dhcp_interface' in ra_conf:
                    dhcp_interface = ra_conf['dhcp_interface']

                    verify_interface_exists(dhcp_interface)
                    dhcp_base = directories['isc_dhclient_dir']

                    if not os.path.exists(f'{dhcp_base}/dhclient_{dhcp_interface}.conf'):
                        raise ConfigError(f"Invalid dhcp-interface on remote-access connection {name}")

                    ipsec['dhcp_interfaces'].add(dhcp_interface)

                    address = get_dhcp_address(dhcp_interface)
                    count = 0
                    while not address and count < dhcp_wait_attempts:
                        address = get_dhcp_address(dhcp_interface)
                        count += 1
                        sleep(dhcp_wait_sleep)

                    if not address:
                        ipsec['dhcp_no_address'][f'ra_{name}'] = dhcp_interface
                        print(f"Failed to get address from dhcp-interface on remote-access connection {name} -- skipped")
                        continue

                if 'esp_group' in ra_conf:
                    if 'esp_group' not in ipsec or ra_conf['esp_group'] not in ipsec['esp_group']:
                        raise ConfigError(f"Invalid esp-group on {name} remote-access config")
                else:
                    raise ConfigError(f"Missing esp-group on {name} remote-access config")

                if 'ike_group' in ra_conf:
                    if 'ike_group' not in ipsec or ra_conf['ike_group'] not in ipsec['ike_group']:
                        raise ConfigError(f"Invalid ike-group on {name} remote-access config")

                    ike = ra_conf['ike_group']
                    if dict_search(f'ike_group.{ike}.key_exchange', ipsec) != 'ikev2':
                        raise ConfigError('IPsec remote-access connections requires IKEv2!')

                else:
                    raise ConfigError(f"Missing ike-group on {name} remote-access config")

                if 'authentication' not in ra_conf:
                    raise ConfigError(f"Missing authentication on {name} remote-access config")

                if ra_conf['authentication']['server_mode'] == 'x509':
                    if 'x509' not in ra_conf['authentication']:
                        raise ConfigError(f"Missing x509 settings on {name} remote-access config")

                    x509 = ra_conf['authentication']['x509']

                    if 'ca_certificate' not in x509 or 'certificate' not in x509:
                        raise ConfigError(f"Missing x509 certificates on {name} remote-access config")

                    verify_pki_x509(ipsec['pki'], x509)
                elif ra_conf['authentication']['server_mode'] == 'pre-shared-secret':
                    if 'pre_shared_secret' not in ra_conf['authentication']:
                        raise ConfigError(f"Missing pre-shared-key on {name} remote-access config")

                if 'client_mode' not in ra_conf['authentication']:
                    raise ConfigError('Client authentication method is required!')

                if dict_search('authentication.client_mode', ra_conf) == 'eap-radius':
                    if dict_search('remote_access.radius.server', ipsec) == None:
                        raise ConfigError('RADIUS authentication requires at least one server')

                if 'pool' in ra_conf:
                    if {'dhcp', 'radius'} <= set(ra_conf['pool']):
                        raise ConfigError(f'Can not use both DHCP and RADIUS for address allocation '\
                                          f'at the same time for "{name}"!')

                    if 'dhcp' in ra_conf['pool'] and len(ra_conf['pool']) > 1:
                        raise ConfigError(f'Can not use DHCP and a predefined address pool for "{name}"!')

                    if 'radius' in ra_conf['pool'] and len(ra_conf['pool']) > 1:
                        raise ConfigError(f'Can not use RADIUS and a predefined address pool for "{name}"!')

                    for pool in ra_conf['pool']:
                        if pool == 'dhcp':
                            if dict_search('remote_access.dhcp.server', ipsec) == None:
                                raise ConfigError('IPsec DHCP server is not configured!')
                        elif pool == 'radius':
                            if dict_search('remote_access.radius.server', ipsec) == None:
                                raise ConfigError('IPsec RADIUS server is not configured!')

                            if dict_search('authentication.client_mode', ra_conf) != 'eap-radius':
                                raise ConfigError('RADIUS IP pool requires eap-radius client authentication!')

                        elif 'pool' not in ipsec['remote_access'] or pool not in ipsec['remote_access']['pool']:
                            raise ConfigError(f'Requested pool "{pool}" does not exist!')

        if 'pool' in ipsec['remote_access']:
            for pool, pool_config in ipsec['remote_access']['pool'].items():
                if 'prefix' not in pool_config:
                    raise ConfigError(f'Missing madatory prefix option for pool "{pool}"!')

                if 'name_server' in pool_config:
                    if len(pool_config['name_server']) > 2:
                        raise ConfigError(f'Only two name-servers are supported for remote-access pool "{pool}"!')

                    for ns in pool_config['name_server']:
                        v4_addr_and_ns = is_ipv4(ns) and not is_ipv4(pool_config['prefix'])
                        v6_addr_and_ns = is_ipv6(ns) and not is_ipv6(pool_config['prefix'])
                        if v4_addr_and_ns or v6_addr_and_ns:
                           raise ConfigError('Must use both IPv4 or IPv6 addresses for pool prefix and name-server adresses!')

                if 'exclude' in pool_config:
                    for exclude in pool_config['exclude']:
                        v4_addr_and_exclude = is_ipv4(exclude) and not is_ipv4(pool_config['prefix'])
                        v6_addr_and_exclude = is_ipv6(exclude) and not is_ipv6(pool_config['prefix'])
                        if v4_addr_and_exclude or v6_addr_and_exclude:
                           raise ConfigError('Must use both IPv4 or IPv6 addresses for pool prefix and exclude prefixes!')

        if 'radius' in ipsec['remote_access'] and 'server' in ipsec['remote_access']['radius']:
            for server, server_config in ipsec['remote_access']['radius']['server'].items():
                if 'key' not in server_config:
                    raise ConfigError(f'Missing RADIUS secret key for server "{server}"')

    if 'site_to_site' in ipsec and 'peer' in ipsec['site_to_site']:
        for peer, peer_conf in ipsec['site_to_site']['peer'].items():
            has_default_esp = False
            # Peer name it is swanctl connection name and shouldn't contain dots or colons, T4118
            if bool(re.search(':|\.', peer)):
                raise ConfigError(f'Incorrect peer name "{peer}" '
                                  f'Peer name can contain alpha-numeric letters, hyphen and underscore')

            if 'remote_address' not in peer_conf:
                print(f'You should set correct remote-address "peer {peer} remote-address x.x.x.x"\n')

            if 'default_esp_group' in peer_conf:
                has_default_esp = True
                if 'esp_group' not in ipsec or peer_conf['default_esp_group'] not in ipsec['esp_group']:
                    raise ConfigError(f"Invalid esp-group on site-to-site peer {peer}")

            if 'ike_group' in peer_conf:
                if 'ike_group' not in ipsec or peer_conf['ike_group'] not in ipsec['ike_group']:
                    raise ConfigError(f"Invalid ike-group on site-to-site peer {peer}")
            else:
                raise ConfigError(f"Missing ike-group on site-to-site peer {peer}")

            if 'authentication' not in peer_conf or 'mode' not in peer_conf['authentication']:
                raise ConfigError(f"Missing authentication on site-to-site peer {peer}")

            if {'id', 'use_x509_id'} <= set(peer_conf['authentication']):
                raise ConfigError(f"Manually set peer id and use-x509-id are mutually exclusive!")

            if peer_conf['authentication']['mode'] == 'x509':
                if 'x509' not in peer_conf['authentication']:
                    raise ConfigError(f"Missing x509 settings on site-to-site peer {peer}")

                x509 = peer_conf['authentication']['x509']

                if 'ca_certificate' not in x509 or 'certificate' not in x509:
                    raise ConfigError(f"Missing x509 certificates on site-to-site peer {peer}")

                verify_pki_x509(ipsec['pki'], x509)
            elif peer_conf['authentication']['mode'] == 'rsa':
                if 'rsa' not in peer_conf['authentication']:
                    raise ConfigError(f"Missing RSA settings on site-to-site peer {peer}")

                rsa = peer_conf['authentication']['rsa']

                if 'local_key' not in rsa:
                    raise ConfigError(f"Missing RSA local-key on site-to-site peer {peer}")

                if 'remote_key' not in rsa:
                    raise ConfigError(f"Missing RSA remote-key on site-to-site peer {peer}")

                verify_pki_rsa(ipsec['pki'], rsa)

            if 'local_address' not in peer_conf and 'dhcp_interface' not in peer_conf:
                raise ConfigError(f"Missing local-address or dhcp-interface on site-to-site peer {peer}")

            if 'dhcp_interface' in peer_conf:
                dhcp_interface = peer_conf['dhcp_interface']

                verify_interface_exists(dhcp_interface)
                dhcp_base = directories['isc_dhclient_dir']

                if not os.path.exists(f'{dhcp_base}/dhclient_{dhcp_interface}.conf'):
                    raise ConfigError(f"Invalid dhcp-interface on site-to-site peer {peer}")

                ipsec['dhcp_interfaces'].add(dhcp_interface)

                address = get_dhcp_address(dhcp_interface)
                count = 0
                while not address and count < dhcp_wait_attempts:
                    address = get_dhcp_address(dhcp_interface)
                    count += 1
                    sleep(dhcp_wait_sleep)

                if not address:
                    ipsec['dhcp_no_address'][f'peer_{peer}'] = dhcp_interface
                    print(f"Failed to get address from dhcp-interface on site-to-site peer {peer} -- skipped")
                    continue

            if 'vti' in peer_conf:
                if 'local_address' in peer_conf and 'dhcp_interface' in peer_conf:
                    raise ConfigError(f"A single local-address or dhcp-interface is required when using VTI on site-to-site peer {peer}")

                if dict_search('options.disable_route_autoinstall',
                               ipsec) == None:
                    Warning('It\'s recommended to use ipsec vti with the next command\n[set vpn ipsec option disable-route-autoinstall]')

                if 'bind' in peer_conf['vti']:
                    vti_interface = peer_conf['vti']['bind']
                    if not interface_exists(vti_interface):
                        raise ConfigError(f'VTI interface {vti_interface} for site-to-site peer {peer} does not exist!')

            if 'vti' not in peer_conf and 'tunnel' not in peer_conf:
                raise ConfigError(f"No VTI or tunnel specified on site-to-site peer {peer}")

            if 'tunnel' in peer_conf:
                for tunnel, tunnel_conf in peer_conf['tunnel'].items():
                    if 'esp_group' not in tunnel_conf and not has_default_esp:
                        raise ConfigError(f"Missing esp-group on tunnel {tunnel} for site-to-site peer {peer}")

                    esp_group_name = tunnel_conf['esp_group'] if 'esp_group' in tunnel_conf else peer_conf['default_esp_group']

                    if esp_group_name not in ipsec['esp_group']:
                        raise ConfigError(f"Invalid esp-group on tunnel {tunnel} for site-to-site peer {peer}")

                    esp_group = ipsec['esp_group'][esp_group_name]

                    if 'mode' in esp_group and esp_group['mode'] == 'transport':
                        if 'protocol' in tunnel_conf and ((peer in ['any', '0.0.0.0']) or ('local_address' not in peer_conf or peer_conf['local_address'] in ['any', '0.0.0.0'])):
                            raise ConfigError(f"Fixed local-address or peer required when a protocol is defined with ESP transport mode on tunnel {tunnel} for site-to-site peer {peer}")

                        if ('local' in tunnel_conf and 'prefix' in tunnel_conf['local']) or ('remote' in tunnel_conf and 'prefix' in tunnel_conf['remote']):
                            raise ConfigError(f"Local/remote prefix cannot be used with ESP transport mode on tunnel {tunnel} for site-to-site peer {peer}")

def cleanup_pki_files():
    for path in [CERT_PATH, CA_PATH, CRL_PATH, KEY_PATH, PUBKEY_PATH]:
        if not os.path.exists(path):
            continue
        for file in os.listdir(path):
            file_path = os.path.join(path, file)
            if os.path.isfile(file_path):
                os.unlink(file_path)

def generate_pki_files_x509(pki, x509_conf):
    for ca_cert_name in x509_conf['ca_certificate']:
        ca_cert_data = dict_search_args(pki, 'ca', ca_cert_name, 'certificate')
        ca_cert_crls = dict_search_args(pki, 'ca', ca_cert_name, 'crl') or []
        crl_index = 1

        with open(os.path.join(CA_PATH, f'{ca_cert_name}.pem'), 'w') as f:
            f.write(wrap_certificate(ca_cert_data))

        for crl in ca_cert_crls:
            with open(os.path.join(CRL_PATH, f'{ca_cert_name}_{crl_index}.pem'), 'w') as f:
                f.write(wrap_crl(crl))
            crl_index += 1

    cert_name = x509_conf['certificate']
    cert_data = dict_search_args(pki, 'certificate', cert_name, 'certificate')
    key_data = dict_search_args(pki, 'certificate', cert_name, 'private', 'key')
    protected = 'passphrase' in x509_conf

    with open(os.path.join(CERT_PATH, f'{cert_name}.pem'), 'w') as f:
        f.write(wrap_certificate(cert_data))

    with open(os.path.join(KEY_PATH, f'x509_{cert_name}.pem'), 'w') as f:
        f.write(wrap_private_key(key_data, protected))

def generate_pki_files_rsa(pki, rsa_conf):
    local_key_name = rsa_conf['local_key']
    local_key_data = dict_search_args(pki, 'key_pair', local_key_name, 'private', 'key')
    protected = 'passphrase' in rsa_conf
    remote_key_name = rsa_conf['remote_key']
    remote_key_data = dict_search_args(pki, 'key_pair', remote_key_name, 'public', 'key')

    local_key = load_private_key(local_key_data, rsa_conf['passphrase'] if protected else None)

    with open(os.path.join(KEY_PATH, f'rsa_{local_key_name}.pem'), 'w') as f:
        f.write(wrap_private_key(local_key_data, protected))

    with open(os.path.join(PUBKEY_PATH, f'{local_key_name}.pem'), 'w') as f:
        f.write(encode_public_key(local_key.public_key()))

    with open(os.path.join(PUBKEY_PATH, f'{remote_key_name}.pem'), 'w') as f:
        f.write(wrap_public_key(remote_key_data))

def generate(ipsec):
    cleanup_pki_files()

    if not ipsec:
        for config_file in [charon_dhcp_conf, charon_radius_conf, interface_conf, swanctl_conf]:
            if os.path.isfile(config_file):
                os.unlink(config_file)
        render(charon_conf, 'ipsec/charon.j2', {'install_routes': default_install_routes})
        return

    if ipsec['dhcp_interfaces']:
        with open(DHCP_HOOK_IFLIST, 'w') as f:
            f.write(" ".join(ipsec['dhcp_interfaces']))
    elif os.path.exists(DHCP_HOOK_IFLIST):
        os.unlink(DHCP_HOOK_IFLIST)

    for path in [swanctl_dir, CERT_PATH, CA_PATH, CRL_PATH, PUBKEY_PATH]:
        if not os.path.exists(path):
            os.mkdir(path, mode=0o755)

    if not os.path.exists(KEY_PATH):
        os.mkdir(KEY_PATH, mode=0o700)

    if 'l2tp' in ipsec:
        if 'authentication' in ipsec['l2tp'] and 'x509' in ipsec['l2tp']['authentication']:
            generate_pki_files_x509(ipsec['pki'], ipsec['l2tp']['authentication']['x509'])

    if 'remote_access' in ipsec and 'connection' in ipsec['remote_access']:
        for rw, rw_conf in ipsec['remote_access']['connection'].items():
            if f'ra_{rw}' in ipsec['dhcp_no_address']:
                continue

            local_ip = ''
            if 'local_address' in rw_conf:
                local_ip = rw_conf['local_address']
            elif 'dhcp_interface' in rw_conf:
                local_ip = get_dhcp_address(rw_conf['dhcp_interface'])

            ipsec['remote_access']['connection'][rw]['local_address'] = local_ip

            if 'authentication' in rw_conf and 'x509' in rw_conf['authentication']:
                generate_pki_files_x509(ipsec['pki'], rw_conf['authentication']['x509'])

    if 'site_to_site' in ipsec and 'peer' in ipsec['site_to_site']:
        for peer, peer_conf in ipsec['site_to_site']['peer'].items():
            if f'peer_{peer}' in ipsec['dhcp_no_address']:
                continue

            if peer_conf['authentication']['mode'] == 'x509':
                generate_pki_files_x509(ipsec['pki'], peer_conf['authentication']['x509'])
            elif peer_conf['authentication']['mode'] == 'rsa':
                generate_pki_files_rsa(ipsec['pki'], peer_conf['authentication']['rsa'])

            local_ip = ''
            if 'local_address' in peer_conf:
                local_ip = peer_conf['local_address']
            elif 'dhcp_interface' in peer_conf:
                local_ip = get_dhcp_address(peer_conf['dhcp_interface'])

            ipsec['site_to_site']['peer'][peer]['local_address'] = local_ip

            if 'tunnel' in peer_conf:
                for tunnel, tunnel_conf in peer_conf['tunnel'].items():
                    local_prefixes = dict_search_args(tunnel_conf, 'local', 'prefix')
                    remote_prefixes = dict_search_args(tunnel_conf, 'remote', 'prefix')

                    if not local_prefixes or not remote_prefixes:
                        continue

                    passthrough = None

                    for local_prefix in local_prefixes:
                        for remote_prefix in remote_prefixes:
                            local_net = ipaddress.ip_network(local_prefix)
                            remote_net = ipaddress.ip_network(remote_prefix)
                            if local_net.overlaps(remote_net):
                                if passthrough is None:
                                    passthrough = []
                                passthrough.append(local_prefix)

                    ipsec['site_to_site']['peer'][peer]['tunnel'][tunnel]['passthrough'] = passthrough

        # auth psk <tag> dhcp-interface <xxx>
        if jmespath.search('authentication.psk.*.dhcp_interface', ipsec):
            for psk, psk_config in ipsec['authentication']['psk'].items():
                if 'dhcp_interface' in psk_config:
                    for iface in psk_config['dhcp_interface']:
                        id = get_dhcp_address(iface)
                        if id:
                            ipsec['authentication']['psk'][psk]['id'].append(id)

    render(charon_conf, 'ipsec/charon.j2', ipsec)
    render(charon_dhcp_conf, 'ipsec/charon/dhcp.conf.j2', ipsec)
    render(charon_radius_conf, 'ipsec/charon/eap-radius.conf.j2', ipsec)
    render(interface_conf, 'ipsec/interfaces_use.conf.j2', ipsec)
    render(swanctl_conf, 'ipsec/swanctl.conf.j2', ipsec)


def apply(ipsec):
    systemd_service = 'strongswan.service'
    if not ipsec:
        call(f'systemctl stop {systemd_service}')
    else:
        call(f'systemctl reload-or-restart {systemd_service}')

        if ipsec.get('nhrp_exists', False):
            try:
                call_dependents()
            except ConfigError:
                # Ignore config errors on dependent due to being called too early. Example:
                # ConfigError("ConfigError('Interface ethN requires an IP address!')")
                pass


if __name__ == '__main__':
    try:
        ipsec = get_config()
        verify(ipsec)
        generate(ipsec)
        apply(ipsec)
    except ConfigError as e:
        print(e)
        exit(1)
