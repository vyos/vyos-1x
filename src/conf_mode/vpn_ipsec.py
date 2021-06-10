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

import os

from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configdict import leaf_node_changed
from vyos.configverify import verify_interface_exists
from vyos.ifconfig import Interface
from vyos.template import render
from vyos.util import call
from vyos.util import dict_search
from vyos.util import get_interface_address
from vyos.util import process_named_running
from vyos.util import run
from vyos.util import cidr_fit
from vyos import ConfigError
from vyos import airbag
airbag.enable()

authby_translate = {
    'pre-shared-secret': 'secret',
    'rsa': 'rsasig',
    'x509': 'rsasig'
}
default_pfs = 'dh-group2'
pfs_translate = {
    'dh-group1': 'modp768',
    'dh-group2': 'modp1024',
    'dh-group5': 'modp1536',
    'dh-group14': 'modp2048',
    'dh-group15': 'modp3072',
    'dh-group16': 'modp4096',
    'dh-group17': 'modp6144',
    'dh-group18': 'modp8192',
    'dh-group19': 'ecp256',
    'dh-group20': 'ecp384',
    'dh-group21': 'ecp512',
    'dh-group22': 'modp1024s160',
    'dh-group23': 'modp2048s224',
    'dh-group24': 'modp2048s256',
    'dh-group25': 'ecp192',
    'dh-group26': 'ecp224',
    'dh-group27': 'ecp224bp',
    'dh-group28': 'ecp256bp',
    'dh-group29': 'ecp384bp',
    'dh-group30': 'ecp512bp',
    'dh-group31': 'curve25519',
    'dh-group32': 'curve448'
}

any_log_modes = [
    'dmn', 'mgr', 'ike', 'chd','job', 'cfg', 'knl', 'net', 'asn',
    'enc', 'lib', 'esp', 'tls', 'tnc', 'imc', 'imv', 'pts'
]

ike_ciphers = {}
esp_ciphers = {}

mark_base = 0x900000

CA_PATH = "/etc/ipsec.d/cacerts/"
CRL_PATH = "/etc/ipsec.d/crls/"

DHCP_BASE = "/var/lib/dhcp/dhclient"

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

    ipsec['interface_change'] = leaf_node_changed(conf, base + ['ipsec-interfaces', 'interface'])
    ipsec['l2tp_exists'] = conf.exists('vpn l2tp remote-access ipsec-settings ')
    ipsec['nhrp_exists'] = conf.exists('protocols nhrp tunnel')
    ipsec['rsa_keys'] = conf.get_config_dict(['vpn', 'rsa-keys'], key_mangling=('-', '_'),
                                             get_first_key=True, no_tag_node_value_mangle=True)

    default_ike_pfs = None

    if 'ike_group' in ipsec:
        for group, ike_conf in ipsec['ike_group'].items():
            if 'proposal' in ike_conf:
                ciphers = []
                for i in ike_conf['proposal']:
                    proposal = ike_conf['proposal'][i]
                    enc = proposal['encryption'] if 'encryption' in proposal else None
                    hash = proposal['hash'] if 'hash' in proposal else None
                    pfs = ('dh-group' + proposal['dh_group']) if 'dh_group' in proposal else default_pfs

                    if not default_ike_pfs:
                        default_ike_pfs = pfs

                    if enc and hash:
                        ciphers.append(f"{enc}-{hash}-{pfs_translate[pfs]}" if pfs else f"{enc}-{hash}")
                ike_ciphers[group] = ','.join(ciphers) + '!'

    if 'esp_group' in ipsec:
        for group, esp_conf in ipsec['esp_group'].items():
            pfs = esp_conf['pfs'] if 'pfs' in esp_conf else 'enable'

            if pfs == 'disable':
                pfs = None

            if pfs == 'enable':
                pfs = default_ike_pfs

            if 'proposal' in esp_conf:
                ciphers = []
                for i in esp_conf['proposal']:
                    proposal = esp_conf['proposal'][i]
                    enc = proposal['encryption'] if 'encryption' in proposal else None
                    hash = proposal['hash'] if 'hash' in proposal else None
                    if enc and hash:
                        ciphers.append(f"{enc}-{hash}-{pfs_translate[pfs]}" if pfs else f"{enc}-{hash}")
                esp_ciphers[group] = ','.join(ciphers) + '!'

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

                if 'key' not in peer_conf['authentication']['x509']:
                    raise ConfigError(f"Missing x509 key on site-to-site peer {peer}")

                if 'ca_cert_file' not in peer_conf['authentication']['x509'] or 'cert_file' not in peer_conf['authentication']['x509']:
                    raise ConfigError(f"Missing x509 settings on site-to-site peer {peer}")

                if 'file' not in peer_conf['authentication']['x509']['key']:
                    raise ConfigError(f"Missing x509 key file on site-to-site peer {peer}")

                for key in ['ca_cert_file', 'cert_file', 'crl_file']:
                    if key in peer_conf['authentication']['x509']:
                        path = os.path.join(X509_PATH, peer_conf['authentication']['x509'][key])
                        if not os.path.exists(path):
                            raise ConfigError(f"File not found for {key} on site-to-site peer {peer}")

                key_path = os.path.join(X509_PATH, peer_conf['authentication']['x509']['key']['file'])
                if not os.path.exists(key_path):
                    raise ConfigError(f"Private key not found on site-to-site peer {peer}")

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

                address = Interface(dhcp_interface).get_addr()
                if not address:
                    raise ConfigError(f"Failed to get address from dhcp-interface on site-to-site peer {peer}")

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

def generate(ipsec):
    data = {}

    if ipsec:
        data = ipsec
        data['authby'] = authby_translate
        data['ciphers'] = {'ike': ike_ciphers, 'esp': esp_ciphers}
        data['marks'] = {}
        data['rsa_local_key'] = verify_rsa_local_key(ipsec)
        data['x509_path'] = X509_PATH

        if 'site_to_site' in data and 'peer' in data['site_to_site']:
            for peer, peer_conf in ipsec['site_to_site']['peer'].items():
                if peer_conf['authentication']['mode'] == 'x509':
                    ca_cert_file = os.path.join(X509_PATH, peer_conf['authentication']['x509']['ca_cert_file'])
                    call(f'cp -f {ca_cert_file} {CA_PATH}')

                    if 'crl_file' in peer_conf['authentication']['x509']:
                        crl_file = os.path.join(X509_PATH, peer_conf['authentication']['x509']['crl_file'])
                        call(f'cp -f {crl_file} {CRL_PATH}')

                local_ip = ''
                if 'local_address' in peer_conf:
                    local_ip = peer_conf['local_address']
                elif 'dhcp_interface' in peer_conf:
                    local_ip = Interface(peer_conf['dhcp_interface']).get_addr()

                data['site_to_site']['peer'][peer]['local_address'] = local_ip

                if 'vti' in peer_conf and 'bind' in peer_conf['vti']:
                    vti_interface = peer_conf['vti']['bind']
                    data['marks'][vti_interface] = get_mark(vti_interface)

                if 'tunnel' in peer_conf:
                    for tunnel, tunnel_conf in peer_conf['tunnel'].items():
                        local_prefixes = dict_search('local.prefix', tunnel_conf)
                        remote_prefixes = dict_search('remote.prefix', tunnel_conf)

                        if not local_prefixes or not remote_prefixes:
                            continue

                        passthrough = False

                        for local_prefix in local_prefixes:
                            for remote_prefix in remote_prefixes:
                                if cidr_fit(local_prefix, remote_prefix):
                                    passthrough = True
                                    break
                        
                        data['site_to_site']['peer'][peer]['tunnel'][tunnel]['passthrough'] = passthrough

        if 'logging' in ipsec and 'log_modes' in ipsec['logging']:
            modes = ipsec['logging']['log_modes']
            level = ipsec['logging']['log_level'] if 'log_level' in ipsec['logging'] else '1'
            if isinstance(modes, str):
                modes = [modes]
            if 'any' in modes:
                modes = any_log_modes
            data['charondebug'] = f' {level}, '.join(modes) + ' ' + level

    render("/etc/ipsec.conf", "ipsec/ipsec.conf.tmpl", data)
    render("/etc/ipsec.secrets", "ipsec/ipsec.secrets.tmpl", data)
    render("/etc/strongswan.d/interfaces_use.conf", "ipsec/interfaces_use.conf.tmpl", data)
    render("/etc/swanctl/swanctl.conf", "ipsec/swanctl.conf.tmpl", data)

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
        should_start = ('profile' in ipsec or dict_search('site_to_site.peer', ipsec))

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

def get_mark(vti_interface):
    vti_num = int(vti_interface.lstrip('vti'))
    return mark_base + vti_num

if __name__ == '__main__':
    try:
        ipsec = get_config()
        verify(ipsec)
        generate(ipsec)
        apply(ipsec)
    except ConfigError as e:
        print(e)
        exit(1)
