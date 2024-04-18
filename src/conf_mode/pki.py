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

import os

from sys import argv
from sys import exit

from vyos.config import Config
from vyos.config import config_dict_merge
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import node_changed
from vyos.configdiff import Diff
from vyos.configdiff import get_config_diff
from vyos.defaults import directories
from vyos.pki import is_ca_certificate
from vyos.pki import load_certificate
from vyos.pki import load_public_key
from vyos.pki import load_openssh_public_key
from vyos.pki import load_openssh_private_key
from vyos.pki import load_private_key
from vyos.pki import load_crl
from vyos.pki import load_dh_parameters
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.dict import dict_search_recursive
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_active
from vyos import ConfigError
from vyos import airbag
airbag.enable()

vyos_certbot_dir = directories['certbot']

# keys to recursively search for under specified path
sync_search = [
    {
        'keys': ['certificate'],
        'path': ['service', 'https'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['interfaces', 'ethernet'],
    },
    {
        'keys': ['certificate', 'ca_certificate', 'dh_params', 'shared_secret_key', 'auth_key', 'crypt_key'],
        'path': ['interfaces', 'openvpn'],
    },
    {
        'keys': ['ca_certificate'],
        'path': ['interfaces', 'sstpc'],
    },
    {
        'keys': ['key'],
        'path': ['protocols', 'rpki', 'cache'],
    },
    {
        'keys': ['certificate', 'ca_certificate', 'local_key', 'remote_key'],
        'path': ['vpn', 'ipsec'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['vpn', 'openconnect'],
    },
    {
        'keys': ['certificate', 'ca_certificate'],
        'path': ['vpn', 'sstp'],
    }
]

# key from other config nodes -> key in pki['changed'] and pki
sync_translate = {
    'certificate': 'certificate',
    'ca_certificate': 'ca',
    'dh_params': 'dh',
    'local_key': 'key_pair',
    'remote_key': 'key_pair',
    'shared_secret_key': 'openvpn',
    'auth_key': 'openvpn',
    'crypt_key': 'openvpn',
    'key': 'openssh',
}

def certbot_delete(certificate):
    if not boot_configuration_complete():
        return
    if os.path.exists(f'{vyos_certbot_dir}/renewal/{certificate}.conf'):
        cmd(f'certbot delete --non-interactive --config-dir {vyos_certbot_dir} --cert-name {certificate}')

def certbot_request(name: str, config: dict, dry_run: bool=True):
    # We do not call certbot when booting the system - there is no need to do so and
    # request new certificates during boot/image upgrade as the certbot configuration
    # is stored persistent under /config - thus we do not open the door to transient
    # errors
    if not boot_configuration_complete():
        return

    domains = '--domains ' + ' --domains '.join(config['domain_name'])
    tmp = f'certbot certonly --non-interactive --config-dir {vyos_certbot_dir} --cert-name {name} '\
          f'--standalone --agree-tos --no-eff-email --expand --server {config["url"]} '\
          f'--email {config["email"]} --key-type rsa --rsa-key-size {config["rsa_key_size"]} '\
          f'{domains}'
    if 'listen_address' in config:
        tmp += f' --http-01-address {config["listen_address"]}'
    # verify() does not need to actually request a cert but only test for plausability
    if dry_run:
        tmp += ' --dry-run'

    cmd(tmp, raising=ConfigError, message=f'ACME certbot request failed for "{name}"!')

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['pki']

    pki = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     no_tag_node_value_mangle=True)

    if len(argv) > 1 and argv[1] == 'certbot_renew':
        pki['certbot_renew'] = {}

    tmp = node_changed(conf, base + ['ca'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'ca' : tmp})

    tmp = node_changed(conf, base + ['certificate'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'certificate' : tmp})

    tmp = node_changed(conf, base + ['dh'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'dh' : tmp})

    tmp = node_changed(conf, base + ['key-pair'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'key_pair' : tmp})

    tmp = node_changed(conf, base + ['openssh'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'openssh' : tmp})

    tmp = node_changed(conf, base + ['openvpn', 'shared-secret'], recursive=True, expand_nodes=Diff.DELETE | Diff.ADD)
    if tmp:
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'openvpn' : tmp})

    # We only merge on the defaults of there is a configuration at all
    if conf.exists(base):
        # We have gathered the dict representation of the CLI, but there are default
        # options which we need to update into the dictionary retrived.
        default_values = conf.get_config_defaults(**pki.kwargs, recursive=True)
        # remove ACME default configuration if unused by CLI
        if 'certificate' in pki:
            for name, cert_config in pki['certificate'].items():
                if 'acme' not in cert_config:
                    # Remove ACME default values
                    del default_values['certificate'][name]['acme']

        # merge CLI and default dictionary
        pki = config_dict_merge(default_values, pki)

    # Certbot triggered an external renew of the certificates.
    # Mark all ACME based certificates as "changed" to trigger
    # update of dependent services
    if 'certificate' in pki and 'certbot_renew' in pki:
        renew = []
        for name, cert_config in pki['certificate'].items():
            if 'acme' in cert_config:
                renew.append(name)
        # If triggered externally by certbot, certificate key is not present in changed
        if 'changed' not in pki: pki.update({'changed':{}})
        pki['changed'].update({'certificate' : renew})

    # We need to get the entire system configuration to verify that we are not
    # deleting a certificate that is still referenced somewhere!
    pki['system'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                         get_first_key=True,
                                         no_tag_node_value_mangle=True)
    D = get_config_diff(conf)

    for search in sync_search:
        for key in search['keys']:
            changed_key = sync_translate[key]
            if 'changed' not in pki or changed_key not in pki['changed']:
                continue

            for item_name in pki['changed'][changed_key]:
                node_present = False
                if changed_key == 'openvpn':
                    node_present = dict_search_args(pki, 'openvpn', 'shared_secret', item_name)
                else:
                    node_present = dict_search_args(pki, changed_key, item_name)

                if node_present:
                    search_dict = dict_search_args(pki['system'], *search['path'])
                    if not search_dict:
                        continue
                    for found_name, found_path in dict_search_recursive(search_dict, key):
                        if isinstance(found_name, list) and item_name not in found_name:
                            continue

                        if isinstance(found_name, str) and found_name != item_name:
                            continue

                        path = search['path']
                        path_str = ' '.join(path + found_path)
                        print(f'PKI: Updating config: {path_str} {item_name}')

                        if path[0] == 'interfaces':
                            ifname = found_path[0]
                            if not D.node_changed_presence(path + [ifname]):
                                set_dependents(path[1], conf, ifname)
                        else:
                            if not D.node_changed_presence(path):
                                set_dependents(path[1], conf)

    return pki

def is_valid_certificate(raw_data):
    # If it loads correctly we're good, or return False
    return load_certificate(raw_data, wrap_tags=True)

def is_valid_ca_certificate(raw_data):
    # Check if this is a valid certificate with CA attributes
    cert = load_certificate(raw_data, wrap_tags=True)
    if not cert:
        return False
    return is_ca_certificate(cert)

def is_valid_public_key(raw_data):
    # If it loads correctly we're good, or return False
    return load_public_key(raw_data, wrap_tags=True)

def is_valid_private_key(raw_data, protected=False):
    # If it loads correctly we're good, or return False
    # With encrypted private keys, we always return true as we cannot ask for password to verify
    if protected:
        return True
    return load_private_key(raw_data, passphrase=None, wrap_tags=True)

def is_valid_openssh_public_key(raw_data, type):
    # If it loads correctly we're good, or return False
    return load_openssh_public_key(raw_data, type)

def is_valid_openssh_private_key(raw_data, protected=False):
    # If it loads correctly we're good, or return False
    # With encrypted private keys, we always return true as we cannot ask for password to verify
    if protected:
        return True
    return load_openssh_private_key(raw_data, passphrase=None, wrap_tags=True)

def is_valid_crl(raw_data):
    # If it loads correctly we're good, or return False
    return load_crl(raw_data, wrap_tags=True)

def is_valid_dh_parameters(raw_data):
    # If it loads correctly we're good, or return False
    return load_dh_parameters(raw_data, wrap_tags=True)

def verify(pki):
    if not pki:
        return None

    if 'ca' in pki:
        for name, ca_conf in pki['ca'].items():
            if 'certificate' in ca_conf:
                if not is_valid_ca_certificate(ca_conf['certificate']):
                    raise ConfigError(f'Invalid certificate on CA certificate "{name}"')

            if 'private' in ca_conf and 'key' in ca_conf['private']:
                private = ca_conf['private']
                protected = 'password_protected' in private

                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on CA certificate "{name}"')

            if 'crl' in ca_conf:
                ca_crls = ca_conf['crl']
                if isinstance(ca_crls, str):
                    ca_crls = [ca_crls]

                for crl in ca_crls:
                    if not is_valid_crl(crl):
                        raise ConfigError(f'Invalid CRL on CA certificate "{name}"')

    if 'certificate' in pki:
        for name, cert_conf in pki['certificate'].items():
            if 'certificate' in cert_conf:
                if not is_valid_certificate(cert_conf['certificate']):
                    raise ConfigError(f'Invalid certificate on certificate "{name}"')

            if 'private' in cert_conf and 'key' in cert_conf['private']:
                private = cert_conf['private']
                protected = 'password_protected' in private

                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on certificate "{name}"')

            if 'acme' in cert_conf:
                if 'domain_name' not in cert_conf['acme']:
                    raise ConfigError(f'At least one domain-name is required to request '\
                                    f'certificate for "{name}" via ACME!')

                if 'email' not in cert_conf['acme']:
                    raise ConfigError(f'An email address is required to request '\
                                    f'certificate for "{name}" via ACME!')

                if 'certbot_renew' not in pki:
                    # Only run the ACME command if something on this entity changed,
                    # as this is time intensive
                    tmp = dict_search('changed.certificate', pki)
                    if tmp != None and name in tmp:
                        certbot_request(name, cert_conf['acme'])

    if 'dh' in pki:
        for name, dh_conf in pki['dh'].items():
            if 'parameters' in dh_conf:
                if not is_valid_dh_parameters(dh_conf['parameters']):
                    raise ConfigError(f'Invalid DH parameters on "{name}"')

    if 'key_pair' in pki:
        for name, key_conf in pki['key_pair'].items():
            if 'public' in key_conf and 'key' in key_conf['public']:
                if not is_valid_public_key(key_conf['public']['key']):
                    raise ConfigError(f'Invalid public key on key-pair "{name}"')

            if 'private' in key_conf and 'key' in key_conf['private']:
                private = key_conf['private']
                protected = 'password_protected' in private
                if not is_valid_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid private key on key-pair "{name}"')

    if 'openssh' in pki:
        for name, key_conf in pki['openssh'].items():
            if 'public' in key_conf and 'key' in key_conf['public']:
                if 'type' not in key_conf['public']:
                    raise ConfigError(f'Must define OpenSSH public key type for "{name}"')
                if not is_valid_openssh_public_key(key_conf['public']['key'], key_conf['public']['type']):
                    raise ConfigError(f'Invalid OpenSSH public key "{name}"')

            if 'private' in key_conf and 'key' in key_conf['private']:
                private = key_conf['private']
                protected = 'password_protected' in private
                if not is_valid_openssh_private_key(private['key'], protected):
                    raise ConfigError(f'Invalid OpenSSH private key "{name}"')

    if 'x509' in pki:
        if 'default' in pki['x509']:
            default_values = pki['x509']['default']
            if 'country' in default_values:
                country = default_values['country']
                if len(country) != 2 or not country.isalpha():
                    raise ConfigError(f'Invalid default country value. Value must be 2 alpha characters.')

    if 'changed' in pki:
        # if the list is getting longer, we can move to a dict() and also embed the
        # search key as value from line 173 or 176
        for search in sync_search:
            for key in search['keys']:
                changed_key = sync_translate[key]

                if changed_key not in pki['changed']:
                    continue

                for item_name in pki['changed'][changed_key]:
                    node_present = False
                    if changed_key == 'openvpn':
                        node_present = dict_search_args(pki, 'openvpn', 'shared_secret', item_name)
                    else:
                        node_present = dict_search_args(pki, changed_key, item_name)

                    if not node_present:
                        search_dict = dict_search_args(pki['system'], *search['path'])

                        if not search_dict:
                            continue

                        for found_name, found_path in dict_search_recursive(search_dict, key):
                            if found_name == item_name:
                                path_str = " ".join(search['path'] + found_path)
                                raise ConfigError(f'PKI object "{item_name}" still in use by "{path_str}"')

    return None

def generate(pki):
    if not pki:
        return None

    # Certbot renewal only needs to re-trigger the services to load up the
    # new PEM file
    if 'certbot_renew' in pki:
        return None

    certbot_list = []
    certbot_list_on_disk = []
    if os.path.exists(f'{vyos_certbot_dir}/live'):
        certbot_list_on_disk = [f.path.split('/')[-1] for f in os.scandir(f'{vyos_certbot_dir}/live') if f.is_dir()]

    if 'certificate' in pki:
        changed_certificates = dict_search('changed.certificate', pki)
        for name, cert_conf in pki['certificate'].items():
            if 'acme' in cert_conf:
                certbot_list.append(name)
                # generate certificate if not found on disk
                if name not in certbot_list_on_disk:
                    certbot_request(name, cert_conf['acme'], dry_run=False)
                elif changed_certificates != None and name in changed_certificates:
                    # when something for the certificate changed, we should delete it
                    if name in certbot_list_on_disk:
                        certbot_delete(name)
                    certbot_request(name, cert_conf['acme'], dry_run=False)

    # Cleanup certbot configuration and certificates if no longer in use by CLI
    # Get foldernames under vyos_certbot_dir which each represent a certbot cert
    if os.path.exists(f'{vyos_certbot_dir}/live'):
        for cert in certbot_list_on_disk:
            if cert not in certbot_list:
                # certificate is no longer active on the CLI - remove it
                certbot_delete(cert)

    return None

def apply(pki):
    systemd_certbot_name = 'certbot.timer'
    if not pki:
        call(f'systemctl stop {systemd_certbot_name}')
        return None

    has_certbot = False
    if 'certificate' in pki:
        for name, cert_conf in pki['certificate'].items():
            if 'acme' in cert_conf:
                has_certbot = True
                break

    if not has_certbot:
        call(f'systemctl stop {systemd_certbot_name}')
    elif has_certbot and not is_systemd_service_active(systemd_certbot_name):
        call(f'systemctl restart {systemd_certbot_name}')

    if 'changed' in pki:
        call_dependents()

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
