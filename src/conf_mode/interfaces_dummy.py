#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import get_interface_dict
from vyos.configverify import verify_vrf
from vyos.configverify import verify_address
from vyos.configverify import verify_bridge_delete
from vyos.configverify import verify_mirror_redirect
from vyos.ifconfig import DummyIf
from vyos.utils.depverify import verify_interface_dependencies
from vyos.utils.dict import dict_search
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrive CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'dummy']
    _, dummy = get_interface_dict(conf, base)

    dummy['int_dependencies'] = verify_interface_dependencies(conf.get_config_dict([], key_mangling=('-', '_'), get_first_key=True),
                                                           dummy['ifname'],
                                                           ignore=f"interfaces dummy {dummy['ifname']}")
    return dummy

def verify(dummy):
    if 'deleted' in dummy:
        verify_bridge_delete(dummy)

        # Check for interface dependencies
        dependency_errors = dict_search('int_dependencies.errors', dummy)
        dependency_warnings = dict_search('int_dependencies.warnings', dummy)
        if dependency_errors:
            raise ConfigError(dummy['int_dependencies']['errors_msg'])
        if dependency_warnings:
            Warning(dummy['int_dependencies']['warnings_msg'])

        return None

    verify_vrf(dummy)
    verify_address(dummy)
    verify_mirror_redirect(dummy)

    return None

def generate(dummy):
    return None

def apply(dummy):
    d = DummyIf(**dummy)

    # Remove dummy interface
    if 'deleted' in dummy:
        d.remove()
    else:
        d.update(dummy)

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
