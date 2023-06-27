#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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


from pathlib import Path

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.ifconfig import Section
from vyos.ifconfig import EthernetIf
from vyos.ifconfig import interface
from vyos.util import call
from vyos.util import rc_cmd
from vyos.template import render
from vyos.xml import defaults

from vyos import ConfigError
from vyos import airbag
from vyos.vpp import VPPControl

airbag.enable()

service_name = 'vpp'
service_conf = Path(f'/run/vpp/{service_name}.conf')
systemd_override = '/run/systemd/system/vpp.service.d/10-override.conf'


def _get_pci_address_by_interface(iface):
    from vyos.util import rc_cmd
    rc, out = rc_cmd(f'ethtool -i {iface}')
    if rc == 0:
        output_lines = out.split('\n')
        for line in output_lines:
            if 'bus-info' in line:
                return line.split(None, 1)[1].strip()


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp']
    base_ethernet = ['interfaces', 'ethernet']
    if not conf.exists(base):
        return None

    config = conf.get_config_dict(base,
                                  get_first_key=True,
                                  key_mangling=('-', '_'),
                                  no_tag_node_value_mangle=True)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    if 'interface' in default_values:
        del default_values['interface']
    config = dict_merge(default_values, config)

    if 'interface' in config:
        for iface, iface_config in config['interface'].items():
            default_values_iface = defaults(base + ['interface'])
            config['interface'][iface] = dict_merge(default_values_iface, config['interface'][iface])

        # Get PCI address auto
        for iface, iface_config in config['interface'].items():
            if iface_config['pci'] == 'auto':
                config['interface'][iface]['pci'] = _get_pci_address_by_interface(iface)

    config['other_interfaces'] = conf.get_config_dict(base_ethernet, key_mangling=('-', '_'),
                                     get_first_key=True, no_tag_node_value_mangle=True)

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if not config:
        return None

    if 'interface' not in config:
        raise ConfigError(f'"interface" is required but not set!')

    if 'cpu' in config:
        if 'corelist_workers' in config['cpu'] and 'main_core' not in config['cpu']:
            raise ConfigError(f'"cpu main-core" is required but not set!')


def generate(config):
    if not config:
        # Remove old config and return
        service_conf.unlink(missing_ok=True)
        return None

    render(service_conf, 'vpp/startup.conf.j2', config)
    render(systemd_override, 'vpp/override.conf.j2', config)

    return None


def apply(config):
    if not config:
        print(f'systemctl stop {service_name}.service')
        call(f'systemctl stop {service_name}.service')
        return
    else:
        print(f'systemctl restart {service_name}.service')
        call(f'systemctl restart {service_name}.service')

    call('systemctl daemon-reload')

    call('sudo sysctl -w vm.nr_hugepages=4096')
    vpp_control = VPPControl()
    for iface, _ in config['interface'].items():
        # Create lcp
        if iface not in Section.interfaces():
            vpp_control.lcp_pair_add(iface, iface)

        # update interface config
        #e = EthernetIf(iface)
        #e.update(config['other_interfaces'][iface])


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
