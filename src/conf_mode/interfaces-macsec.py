#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.ifconfig import MACsecIf
from vyos.template import render
from vyos.util import call
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_source_interface
from vyos import ConfigError
from vyos import airbag
airbag.enable()

# XXX: wpa_supplicant works on the source interface
wpa_suppl_conf = '/run/wpa_supplicant/{source_interface}.conf'

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'macsec']
    macsec = get_interface_dict(conf, base)

    # Check if interface has been removed
    if 'deleted' in macsec:
        source_interface = conf.return_effective_value(
                base + ['source-interface'])
        macsec.update({'source_interface': source_interface})

    return macsec


def verify(macsec):
    if 'deleted' in macsec:
        verify_bridge_delete(macsec)
        return None

    verify_source_interface(macsec)
    verify_vrf(macsec)
    verify_address(macsec)

    if not (('security' in macsec) and
            ('cipher' in macsec['security'])):
        raise ConfigError(
            'Cipher suite must be set for MACsec "{ifname}"'.format(**macsec))

    if (('security' in macsec) and
        ('encrypt' in macsec['security'])):
        tmp = macsec.get('security')

        if not (('mka' in tmp) and
                ('cak' in tmp['mka']) and
                ('ckn' in tmp['mka'])):
            raise ConfigError('Missing mandatory MACsec security '
                              'keys as encryption is enabled!')

    return None


def generate(macsec):
    render(wpa_suppl_conf.format(**macsec),
           'macsec/wpa_supplicant.conf.tmpl', macsec)
    return None


def apply(macsec):
    # Remove macsec interface
    if 'deleted' in macsec.keys():
        call('systemctl stop wpa_supplicant-macsec@{source_interface}'
             .format(**macsec))

        MACsecIf(macsec['ifname']).remove()

        # delete configuration on interface removal
        if os.path.isfile(wpa_suppl_conf.format(**macsec)):
            os.unlink(wpa_suppl_conf.format(**macsec))

    else:
        # This is a special type of interface which needs additional parameters
        # when created using iproute2. Instead of passing a ton of arguments,
        # use a dictionary provided by the interface class which holds all the
        # options necessary.
        conf = MACsecIf.get_config()
        conf['source_interface'] = macsec['source_interface']
        conf['security_cipher'] = macsec['security']['cipher']

        # It is safe to "re-create" the interface always, there is a sanity
        # check that the interface will only be create if its non existent
        i = MACsecIf(macsec['ifname'], **conf)
        i.update(macsec)

        call('systemctl restart wpa_supplicant-macsec@{source_interface}'
             .format(**macsec))

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
