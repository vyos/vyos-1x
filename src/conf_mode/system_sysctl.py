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

import os

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.template import render
from vyos.utils.process import cmdl
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file = r'/run/sysctl/99-vyos-sysctl.conf'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'sysctl']
    if not conf.exists(base):
        return None

    sysctl = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True,
                                  no_tag_node_value_mangle=True)

    # VPP sizes its netlink receive buffer up to net.core.rmem_max every time it
    # (re)opens its netlink socket - do not let a lower value cap it (T9484)
    rmem_max = sysctl.get('parameter', {}).get('net.core.rmem_max', {})
    value = rmem_max.get('value', '')
    if conf.exists(['vpp']) and value.isdigit():
        try:
            from vyos.vpp.config_resource_checks.resource_defaults import (
                default_resource_map,
            )
        except ImportError:
            # VPP is not installed
            default_resource_map = {}

        required = default_resource_map.get('netlink_rx_buffer_size', 0)
        if int(value) < required:
            sysctl['vpp_rmem_max_configured'] = value
            rmem_max['value'] = str(required)

    return sysctl

def verify(sysctl):
    if sysctl and 'vpp_rmem_max_configured' in sysctl:
        Warning(
            f'net.core.rmem_max {sysctl["vpp_rmem_max_configured"]} is below '
            f'what VPP requires, using {sysctl["parameter"]["net.core.rmem_max"]["value"]}!'
        )
    return None

def generate(sysctl):
    if not sysctl:
        if os.path.isfile(config_file):
            os.unlink(config_file)
        return None

    render(config_file, 'system/sysctl.conf.j2', sysctl)
    return None

def apply(sysctl):
    if not sysctl:
        return None

    # We silently ignore all errors
    # See: https://bugzilla.redhat.com/show_bug.cgi?id=1264080
    cmdl(['sysctl', '-f', config_file])
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
