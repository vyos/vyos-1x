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

from copy import deepcopy
from subprocess import DEVNULL
from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configdiff import ConfigDiff
from vyos.template import render
from vyos.util import call, get_interface_address, process_named_running, run, cidr_fit
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

ike_ciphers = {}
esp_ciphers = {}

marks = {}
mark_base = 0x900000
mark_index = 1

CA_PATH = "/etc/ipsec.d/cacerts"
CRL_PATH = "/etc/ipsec.d/crls"

DHCP_BASE = "/var/lib/dhcp/dhclient"

LOCAL_KEY_PATHS = ['/config/auth/', '/config/ipsec.d/rsa-keys/']
X509_PATH = '/config/auth/'

conf = None

def resync_l2tp(conf):
    if not conf.exists('vpn l2tp remote-access ipsec-settings '):
        return

    tmp = run('/usr/libexec/vyos/conf_mode/ipsec-settings.py')
    if tmp > 0:
        print('ERROR: failed to reapply L2TP IPSec settings!')

def resync_nhrp(conf):
    if not conf.exists('protocols nhrp tunnel'):
        return

    run('/opt/vyatta/sbin/vyos-update-nhrp.pl --set_ipsec')

def get_config(config=None):
    global conf
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'ipsec']
    if not conf.exists(base):
        return None

    # retrieve common dictionary keys
    ipsec = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)

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

def verify(ipsec):
    if not ipsec:
        return None

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

                if 'key' not in peer_conf['authentication']['x509'] or 'ca_cert_file' not in peer_conf['authentication']['x509'] or 'cert_file' not in peer_conf['authentication']['x509']:
                    raise ConfigError(f"Missing x509 settings on site-to-site peer {peer}")

                if 'file' not in peer_conf['authentication']['x509']['key']:
                    raise ConfigError(f"Missing x509 settings on site-to-site peer {peer}")

                for key in ['ca_cert_file', 'cert_file', 'crl_file']:
                    if key in peer_conf['authentication']['x509']:
                        path = peer_conf['authentication']['x509'][key]
                        if not os.path.exists(path if path.startswith(X509_PATH) else (X509_PATH + path)):
                            raise ConfigError(f"File not found for {key} on site-to-site peer {peer}")

                key_path = peer_conf['authentication']['x509']['key']['file']
                if not os.path.exists(key_path if key_path.startswith(X509_PATH) else (X509_PATH + key_path)):
                    raise ConfigError(f"Private key not found on site-to-site peer {peer}")

            if peer_conf['authentication']['mode'] == 'rsa':
                if not verify_rsa_local_key():
                    raise ConfigError(f"Invalid key on rsa-keys local-key")

                if 'rsa_key_name' not in peer_conf['authentication']:
                    raise ConfigError(f"Missing rsa-key-name on site-to-site peer {peer}")

                if not verify_rsa_key(peer_conf['authentication']['rsa_key_name']):
                    raise ConfigError(f"Invalid rsa-key-name on site-to-site peer {peer}")

            if 'local_address' not in peer_conf and 'dhcp_interface' not in peer_conf:
                raise ConfigError(f"Missing local-address or dhcp-interface on site-to-site peer {peer}")

            if 'dhcp_interface' in peer_conf:
                dhcp_interface = peer_conf['dhcp_interface']
                if not os.path.exists(f'{DHCP_BASE}_{dhcp_interface}.conf'):
                    raise ConfigError(f"Invalid dhcp-interface on site-to-site peer {peer}")

            if 'vti' in peer_conf:
                if 'local_address' in peer_conf and 'dhcp_interface' in peer_conf:
                    raise ConfigError(f"A single local-address or dhcp-interface is required when using VTI on site-to-site peer {peer}")

                if 'bind' in peer_conf['vti']:
                    vti_interface = peer_conf['vti']['bind']
                    if not get_vti_interface(vti_interface):
                        raise ConfigError(f'Invalid VTI interface on site-to-site peer {peer}')

            if 'vti' not in peer_conf and 'tunnel' not in peer_conf:
                raise ConfigError(f"No vti or tunnels specified on site-to-site peer {peer}")

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

def get_rsa_local_key():
    global conf
    base = ['vpn', 'rsa-keys']
    if not conf.exists(base + ['local-key', 'file']):
        return False

    return conf.return_value(base + ['local-key', 'file'])

def verify_rsa_local_key():
    file = get_rsa_local_key()

    if not file:
        return False

    for path in LOCAL_KEY_PATHS:
        if os.path.exists(path + file):
            return path + file

    return False

def verify_rsa_key(key_name):
    global conf
    base = ['vpn', 'rsa-keys']
    if not conf.exists(base):
        return False
    return conf.exists(base + ['rsa-key-name', key_name, 'rsa-key'])

def generate(ipsec):
    data = {}

    if ipsec:
        data = deepcopy(ipsec)

        if 'site_to_site' in data and 'peer' in data['site_to_site']:
            for peer, peer_conf in ipsec['site_to_site']['peer'].items():
                if peer_conf['authentication']['mode'] == 'x509':
                    ca_cert_file = peer_conf['authentication']['x509']['ca_cert_file']
                    crl_file = peer_conf['authentication']['x509']['crl_file'] if 'crl_file' in peer_conf['authentication']['x509'] else None

                    if not ca_cert_file.startswith(X509_PATH):
                        ca_cert_file = (X509_PATH + ca_cert_file)

                    if crl_file and not crl_file.startswith(X509_PATH):
                        crl_file = (X509_PATH + crl_file)

                    call(f'cp -f {ca_cert_file} {CA_PATH}/')
                    if crl_file:
                        call(f'cp -f {crl_file} {CRL_PATH}/')

                local_ip = ''
                if 'local_address' in peer_conf:
                    local_ip = peer_conf['local_address']
                elif 'dhcp_interface' in peer_conf:
                    local_ip = get_dhcp_address(peer_conf['dhcp_interface'])

                data['site_to_site']['peer'][peer]['local_address'] = local_ip

                if 'vti' in peer_conf and 'bind' in peer_conf['vti']:
                    vti_interface = peer_conf['vti']['bind']
                    get_mark(vti_interface)
                else:
                    for tunnel, tunnel_conf in peer_conf['tunnel'].items():
                        if ('local' not in tunnel_conf or 'prefix' not in tunnel_conf['local']) or ('remote' not in tunnel_conf or 'prefix' not in tunnel_conf['remote']):
                            continue
                        local_prefix = tunnel_conf['local']['prefix']
                        remote_prefix = tunnel_conf['remote']['prefix']
                        passthrough = cidr_fit(local_prefix, remote_prefix)
                        data['site_to_site']['peer'][peer]['tunnel'][tunnel]['passthrough'] = passthrough

        data['authby'] = authby_translate
        data['ciphers'] = {'ike': ike_ciphers, 'esp': esp_ciphers}
        data['marks'] = marks
        data['rsa_local_key'] = verify_rsa_local_key()
        data['x509_path'] = X509_PATH

        if 'logging' in ipsec and 'log_modes' in ipsec['logging']:
            modes = ipsec['logging']['log_modes']
            level = ipsec['logging']['log_level'] if 'log_level' in ipsec['logging'] else '1'
            if isinstance(modes, str): modes = [modes]
            if 'any' in modes:
                modes = ['dmn', 'mgr', 'ike', 'chd', 'job', 'cfg', 'knl', 'net', 'asn', 'enc', 'lib', 'esp', 'tls', 'tnc', 'imc', 'imv', 'pts']
            data['charondebug'] = f' {level}, '.join(modes) + ' ' + level

    render("/etc/ipsec.conf", "ipsec/ipsec.conf.tmpl", data)
    render("/etc/ipsec.secrets", "ipsec/ipsec.secrets.tmpl", data)
    render("/etc/swanctl/swanctl.conf", "ipsec/swanctl.conf.tmpl", data)

def apply(ipsec):
    if not ipsec:
        if conf.exists('vpn l2tp '):
            call('sudo /usr/sbin/ipsec rereadall')
            call('sudo /usr/sbin/ipsec reload')
            call('sudo /usr/sbin/swanctl -q')
        else:
            call('sudo /usr/sbin/ipsec stop')

        resync_l2tp(conf)
        resync_nhrp(conf)
        return

    diff = ConfigDiff(conf, key_mangling=('-', '_'))
    diff.set_level(['vpn', 'ipsec'])

    old_if, new_if = diff.get_value_diff(['ipsec-interfaces', 'interface'])
    interface_change = (old_if != new_if)

    should_start = ('profile' in ipsec or ('site_to_site' in ipsec and 'peer' in ipsec['site_to_site']))

    if not process_named_running('charon'):
        args = ''
        if 'auto_update' in ipsec:
            args = f'--auto-update {ipsec["auto_update"]}'

        if should_start:
            call(f'sudo /usr/sbin/ipsec start {args}')
    else:
        if not should_start:
            call('sudo /usr/sbin/ipsec stop')
        elif interface_change:
            call('sudo /usr/sbin/ipsec restart')
        else:
            call('sudo /usr/sbin/ipsec rereadall')
            call('sudo /usr/sbin/ipsec reload')

    if should_start:
        sleep(2) # Give charon enough time to start
        call('sudo /usr/sbin/swanctl -q')

    resync_l2tp(conf)
    resync_nhrp(conf)

def get_vti_interface(vti_interface):
    global conf
    section = conf.get_config_dict(['interfaces', 'vti'], get_first_key=True)
    for interface, interface_conf in section.items():
        if interface == vti_interface:
            return interface_conf
    return None

def get_mark(vti_interface):
    global mark_base, mark_index
    if vti_interface not in marks:
        marks[vti_interface] = mark_base + mark_index
        mark_index += 1
    return marks[vti_interface]

def get_dhcp_address(interface):
    addr = get_interface_address(interface)
    if not addr:
        return None
    if len(addr['addr_info']) == 0:
        return None
    return addr['addr_info'][0]['local']

if __name__ == '__main__':
    try:
        ipsec = get_config()
        verify(ipsec)
        generate(ipsec)
        apply(ipsec)
    except ConfigError as e:
        print(e)
        exit(1)
