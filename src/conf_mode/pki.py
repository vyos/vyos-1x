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

from sys import exit

import jmespath

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.pki import is_ca_certificate
from vyos.pki import load_certificate
from vyos.pki import load_certificate_request
from vyos.pki import load_public_key
from vyos.pki import load_private_key
from vyos.pki import load_crl
from vyos.pki import load_dh_parameters
from vyos.util import ask_input
from vyos.util import dict_search_recursive
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['pki']

    pki = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     get_first_key=True,
                                     no_tag_node_value_mangle=True)

    pki['changed'] = {}
    tmp = node_changed(conf, base + ['ca'], key_mangling=('-', '_'))
    if tmp: pki['changed'].update({'ca' : tmp})

    tmp = node_changed(conf, base + ['certificate'], key_mangling=('-', '_'))
    if tmp: pki['changed'].update({'certificate' : tmp})

    # We only merge on the defaults of there is a configuration at all
    if conf.exists(base):
        default_values = defaults(base)
        pki = dict_merge(default_values, pki)

    # We need to get the entire system configuration to verify that we are not
    # deleting a certificate that is still referenced somewhere!
    pki['system'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                         get_first_key=True,
                                         no_tag_node_value_mangle=True)

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
        for cert_type in ['ca', 'certificate']:
            if not cert_type in pki['changed']:
                continue
            for certificate in pki['changed'][cert_type]:
                if cert_type not in pki or certificate not in pki['changed'][cert_type]:
                    if cert_type == 'ca':
                        if certificate in dict_search_recursive(pki['system'], 'ca_certificate'):
                            raise ConfigError(f'CA certificate "{certificate}" is still in use!')
                    elif cert_type == 'certificate':
                        if certificate in dict_search_recursive(pki['system'], 'certificate'):
                            raise ConfigError(f'Certificate "{certificate}" is still in use!')

    return None

def generate(pki):
    if not pki:
        return None

    return None

def apply(pki):
    if not pki:
        return None

    # XXX: restart services if the content of a certificate changes

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
