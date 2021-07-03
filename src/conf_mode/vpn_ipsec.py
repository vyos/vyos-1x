#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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

from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_interface_exists
from vyos.configdict import dict_merge
from vyos.ifconfig import Interface
from vyos.pki import wrap_certificate
from vyos.pki import wrap_crl
from vyos.pki import wrap_public_key
from vyos.pki import wrap_private_key
from vyos.template import ip_from_cidr
from vyos.template import render
from vyos.validate import is_ipv6_link_local
from vyos.util import call
from vyos.util import dict_search
from vyos.util import process_named_running
from vyos.util import run
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

dhcp_wait_attempts = 2
dhcp_wait_sleep = 1

swanctl_dir    = '/etc/swanctl'
ipsec_conf     = '/etc/ipsec.conf'
ipsec_secrets  = '/etc/ipsec.secrets'
interface_conf = '/etc/strongswan.d/interfaces_use.conf'
swanctl_conf   = f'{swanctl_dir}/swanctl.conf'

CERT_PATH = f'{swanctl_dir}/x509/'
KEY_PATH  = f'{swanctl_dir}/private/'
CA_PATH   = f'{swanctl_dir}/x509ca/'
CRL_PATH  = f'{swanctl_dir}/x509crl/'

DHCP_BASE = '/var/lib/dhcp/dhclient'
DHCP_HOOK_IFLIST = '/tmp/ipsec_dhcp_waiting'

LOCAL_KEY_PATHS = ['/config/auth/', '/config/ipsec.d/rsa-keys/']
X509_PATH = '/config/auth/'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'ipsec']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipsec = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 get_first_key=True, no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    # XXX: T2665: we must safely remove default values for tag nodes, those are
    # added in a more fine grained way later on
    del default_values['esp_group']
    del default_values['ike_group']
    ipsec = dict_merge(default_values, ipsec)

    if 'esp_group' in ipsec:
        default_values = defaults(base + ['esp-group'])
        for group in ipsec['esp_group']:
            ipsec['esp_group'][group] = dict_merge(default_values,
                                                   ipsec['esp_group'][group])

    if 'ike_group' in ipsec:
        default_values = defaults(base + ['ike-group'])
        for group in ipsec['ike_group']:
            ipsec['ike_group'][group] = dict_merge(default_values,
                                                   ipsec['ike_group'][group])

    ipsec['dhcp_no_address'] = {}
    ipsec['interface_change'] = leaf_node_changed(conf, base + ['ipsec-interfaces',
                                                                'interface'])
    ipsec['l2tp_exists'] = conf.exists(['vpn', 'l2tp', 'remote-access',
                                        'ipsec-settings'])
    ipsec['nhrp_exists'] = conf.exists(['protocols', 'nhrp', 'tunnel'])
    ipsec['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                             get_first_key=True,
                                             no_tag_node_value_mangle=True)
    ipsec['rsa_keys'] = conf.get_config_dict(['vpn', 'rsa-keys'],
                                             key_mangling=('-', '_'),
                                             get_first_key=True,
                                             no_tag_node_value_mangle=True)

    return ipsec

def get_rsa_local_key(ipsec):
    return dict_search('local_key.file', ipsec['rsa_keys'])

def verify_rsa_local_key(ipsec):
    file = get_rsa_local_key(ipsec)

    if not file:
        return False

    for path in LOCAL_KEY_PATHS:
        full_path = os.path.join(path, file)
        if os.path.exists(full_path):
            return full_path

    return False

def verify_rsa_key(ipsec, key_name):
    return dict_search(f'rsa_key_name.{key_name}.rsa_key', ipsec['rsa_keys'])

def get_dhcp_address(iface):
    addresses = Interface(iface).get_addr()
    if not addresses:
        return None
    for address in addresses:
        if not is_ipv6_link_local(address):
            return ip_from_cidr(address)
    return None

def verify_pki(pki, x509_conf):
    if not pki or 'ca' not in pki or 'certificate' not in pki:
        raise ConfigError(f'PKI is not configured')

    ca_cert_name = x509_conf['ca_certificate']
    cert_name = x509_conf['certificate']

    if not dict_search(f'ca.{ca_cert_name}.certificate', ipsec['pki']):
        raise ConfigError(f'Missing CA certificate on specified PKI CA certificate "{ca_cert_name}"')

    if not dict_search(f'certificate.{cert_name}.certificate', ipsec['pki']):
        raise ConfigError(f'Missing certificate on specified PKI certificate "{cert_name}"')

    if not dict_search(f'certificate.{cert_name}.private.key', ipsec['pki']):
        raise ConfigError(f'Missing private key on specified PKI certificate "{cert_name}"')

    return True

def verify(ipsec):
    if not ipsec:
        return None

    if 'ipsec_interfaces' in ipsec and 'interface' in ipsec['ipsec_interfaces']:
        interfaces = ipsec['ipsec_interfaces']['interface']
        if isinstance(interfaces, str):
            interfaces = [interfaces]

        for ifname in interfaces:
            verify_interface_exists(ifname)

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

    if 'site_to_site' in ipsec and 'peer' in ipsec['site_to_site']:
        for peer, peer_conf in ipsec['site_to_site']['peer'].items():
            has_default_esp = False
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

            if peer_conf['authentication']['mode'] == 'x509':
                if 'x509' not in peer_conf['authentication']:
                    raise ConfigError(f"Missing x509 settings on site-to-site peer {peer}")

                x509 = peer_conf['authentication']['x509']

                if 'ca_certificate' not in x509 or 'certificate' not in x509:
                    raise ConfigError(f"Missing x509 certificates on site-to-site peer {peer}")

                verify_pki(ipsec['pki'], x509)

            if peer_conf['authentication']['mode'] == 'rsa':
                if not verify_rsa_local_key(ipsec):
                    raise ConfigError(f"Invalid key on rsa-keys local-key")

                if 'rsa_key_name' not in peer_conf['authentication']:
                    raise ConfigError(f"Missing rsa-key-name on site-to-site peer {peer}")

                if not verify_rsa_key(ipsec, peer_conf['authentication']['rsa_key_name']):
                    raise ConfigError(f"Invalid rsa-key-name on site-to-site peer {peer}")

            if 'local_address' not in peer_conf and 'dhcp_interface' not in peer_conf:
                raise ConfigError(f"Missing local-address or dhcp-interface on site-to-site peer {peer}")

            if 'dhcp_interface' in peer_conf:
                dhcp_interface = peer_conf['dhcp_interface']

                verify_interface_exists(dhcp_interface)

                if not os.path.exists(f'{DHCP_BASE}_{dhcp_interface}.conf'):
                    raise ConfigError(f"Invalid dhcp-interface on site-to-site peer {peer}")

                address = get_dhcp_address(dhcp_interface)
                count = 0
                while not address and count < dhcp_wait_attempts:
                    address = get_dhcp_address(dhcp_interface)
                    count += 1
                    sleep(dhcp_wait_sleep)

                if not address:
                    ipsec['dhcp_no_address'][peer] = dhcp_interface
                    print(f"Failed to get address from dhcp-interface on site-to-site peer {peer} -- skipped")
                    continue

            if 'vti' in peer_conf:
                if 'local_address' in peer_conf and 'dhcp_interface' in peer_conf:
                    raise ConfigError(f"A single local-address or dhcp-interface is required when using VTI on site-to-site peer {peer}")

                if 'bind' in peer_conf['vti']:
                    vti_interface = peer_conf['vti']['bind']
                    if not os.path.exists(f'/sys/class/net/{vti_interface}'):
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

def generate_pki_files(pki, x509_conf):
    ca_cert_name = x509_conf['ca_certificate']
    ca_cert_data = dict_search(f'ca.{ca_cert_name}.certificate', pki)
    ca_cert_crls = dict_search(f'ca.{ca_cert_name}.crl', pki) or []
    crl_index = 1

    cert_name = x509_conf['certificate']
    cert_data = dict_search(f'certificate.{cert_name}.certificate', pki)
    key_data = dict_search(f'certificate.{cert_name}.private.key', pki)
    protected = 'passphrase' in x509_conf

    with open(os.path.join(CA_PATH, f'{ca_cert_name}.pem'), 'w') as f:
        f.write(wrap_certificate(ca_cert_data))

    for crl in ca_cert_crls:
        with open(os.path.join(CRL_PATH, f'{ca_cert_name}_{crl_index}.pem'), 'w') as f:
            f.write(wrap_crl(crl))
        crl_index += 1

    with open(os.path.join(CERT_PATH, f'{cert_name}.pem'), 'w') as f:
        f.write(wrap_certificate(cert_data))

    with open(os.path.join(KEY_PATH, f'{cert_name}.pem'), 'w') as f:
        f.write(wrap_private_key(key_data, protected))

def generate(ipsec):
    if not ipsec:
        for config_file in [ipsec_conf, ipsec_secrets, interface_conf, swanctl_conf]:
            if os.path.isfile(config_file):
                os.unlink(config_file)
        return

    if ipsec['dhcp_no_address']:
        with open(DHCP_HOOK_IFLIST, 'w') as f:
            f.write(" ".join(ipsec['dhcp_no_address'].values()))

    data = ipsec
    data['rsa_local_key'] = verify_rsa_local_key(ipsec)

    for path in [swanctl_dir, CERT_PATH, CA_PATH, CRL_PATH]:
        if not os.path.exists(path):
            os.mkdir(path, mode=0o755)

    if not os.path.exists(KEY_PATH):
        os.mkdir(KEY_PATH, mode=0o700)

    if 'site_to_site' in data and 'peer' in data['site_to_site']:
        for peer, peer_conf in ipsec['site_to_site']['peer'].items():
            if peer in ipsec['dhcp_no_address']:
                continue

            if peer_conf['authentication']['mode'] == 'x509':
                generate_pki_files(ipsec['pki'], peer_conf['authentication']['x509'])

            local_ip = ''
            if 'local_address' in peer_conf:
                local_ip = peer_conf['local_address']
            elif 'dhcp_interface' in peer_conf:
                local_ip = get_dhcp_address(peer_conf['dhcp_interface'])

            data['site_to_site']['peer'][peer]['local_address'] = local_ip

            if 'tunnel' in peer_conf:
                for tunnel, tunnel_conf in peer_conf['tunnel'].items():
                    local_prefixes = dict_search('local.prefix', tunnel_conf)
                    remote_prefixes = dict_search('remote.prefix', tunnel_conf)

                    if not local_prefixes or not remote_prefixes:
                        continue

                    passthrough = []

                    for local_prefix in local_prefixes:
                        for remote_prefix in remote_prefixes:
                            local_net = ipaddress.ip_network(local_prefix)
                            remote_net = ipaddress.ip_network(remote_prefix)
                            if local_net.overlaps(remote_net):
                                passthrough.append(local_prefix)

                    data['site_to_site']['peer'][peer]['tunnel'][tunnel]['passthrough'] = passthrough


    render(ipsec_conf, 'ipsec/ipsec.conf.tmpl', data)
    render(ipsec_secrets, 'ipsec/ipsec.secrets.tmpl', data)
    render(interface_conf, 'ipsec/interfaces_use.conf.tmpl', data)
    render(swanctl_conf, 'ipsec/swanctl.conf.tmpl', data)

def resync_l2tp(ipsec):
    if ipsec and not ipsec['l2tp_exists']:
        return

    tmp = run('/usr/libexec/vyos/conf_mode/ipsec-settings.py')
    if tmp > 0:
        print('ERROR: failed to reapply L2TP IPSec settings!')

def resync_nhrp(ipsec):
    if ipsec and not ipsec['nhrp_exists']:
        return

    tmp = run('/usr/libexec/vyos/conf_mode/protocols_nhrp.py')
    if tmp > 0:
        print('ERROR: failed to reapply NHRP settings!')

def apply(ipsec):
    if not ipsec:
        call('sudo /usr/sbin/ipsec stop')
    else:
        should_start = 'profile' in ipsec or dict_search('site_to_site.peer', ipsec)

        if not process_named_running('charon') and should_start:
            args = f'--auto-update {ipsec["auto_update"]}' if 'auto_update' in ipsec else ''
            call(f'sudo /usr/sbin/ipsec start {args}')
        elif not should_start:
            call('sudo /usr/sbin/ipsec stop')
        elif ipsec['interface_change']:
            call('sudo /usr/sbin/ipsec restart')
        else:
            call('sudo /usr/sbin/ipsec rereadall')
            call('sudo /usr/sbin/ipsec reload')

        if should_start:
            sleep(2) # Give charon enough time to start
            call('sudo /usr/sbin/swanctl -q')

    resync_l2tp(ipsec)
    resync_nhrp(ipsec)

if __name__ == '__main__':
    try:
        ipsec = get_config()
        verify(ipsec)
        generate(ipsec)
        apply(ipsec)
    except ConfigError as e:
        print(e)
        exit(1)
