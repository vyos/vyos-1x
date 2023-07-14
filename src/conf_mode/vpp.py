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

import os
from psutil import virtual_memory

from pathlib import Path
from re import search as re_search, MULTILINE as re_M

from vyos.config import Config
from vyos.configdep import set_dependents, call_dependents
from vyos.configdict import dict_merge
from vyos.configdict import node_changed
from vyos.ifconfig import Section
from vyos.utils.boot import boot_configuration_complete
from vyos.utils.process import call
from vyos.utils.process import rc_cmd
from vyos.utils.system import sysctl_read
from vyos.utils.system import sysctl_apply
from vyos.template import render
from vyos.xml import defaults

from vyos import ConfigError
from vyos import airbag
from vyos.vpp import VPPControl
from vyos.vpp import HostControl

airbag.enable()

service_name = 'vpp'
service_conf = Path(f'/run/vpp/{service_name}.conf')
systemd_override = '/run/systemd/system/vpp.service.d/10-override.conf'

# Free memory required for VPP
# 2 GB for hugepages + 1 GB for other services
MIN_AVAILABLE_MEMORY: int = 3 * 1024**3


def _get_pci_address_by_interface(iface) -> str:
    rc, out = rc_cmd(f'ethtool -i {iface}')
    # if ethtool command was successful
    if rc == 0 and out:
        regex_filter = r'^bus-info: (?P<address>\w+:\w+:\w+\.\w+)$'
        re_obj = re_search(regex_filter, out, re_M)
        # if bus-info with PCI address found
        if re_obj:
            address = re_obj.groupdict().get('address', '')
            return address
    # use VPP - maybe interface already attached to it
    vpp_control = VPPControl(attempts=20, interval=500)
    pci_addr = vpp_control.get_pci_addr(iface)
    if pci_addr:
        return pci_addr
    # raise error if PCI address was not found
    raise ConfigError(f'Cannot find PCI address for interface {iface}')


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['vpp']
    base_ethernet = ['interfaces', 'ethernet']

    # find interfaces removed from VPP
    removed_ifaces = []
    tmp = node_changed(conf, base + ['interface'])
    if tmp:
        for removed_iface in tmp:
            pci_address: str = _get_pci_address_by_interface(removed_iface)
            removed_ifaces.append({
                'iface_name': removed_iface,
                'iface_pci_addr': pci_address
            })
            # add an interface to a list of interfaces that need
            # to be reinitialized after the commit
            set_dependents('ethernet', conf, removed_iface)

    if not conf.exists(base):
        return {'removed_ifaces': removed_ifaces}

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
            # add an interface to a list of interfaces that need
            # to be reinitialized after the commit
            set_dependents('ethernet', conf, iface)

        # Get PCI address auto
        for iface, iface_config in config['interface'].items():
            if iface_config['pci'] == 'auto':
                config['interface'][iface]['pci'] = _get_pci_address_by_interface(iface)

    config['other_interfaces'] = conf.get_config_dict(base_ethernet, key_mangling=('-', '_'),
                                     get_first_key=True, no_tag_node_value_mangle=True)

    if removed_ifaces:
        config['removed_ifaces'] = removed_ifaces

    return config


def verify(config):
    # bail out early - looks like removal from running config
    if not config or (len(config) == 1 and 'removed_ifaces' in config):
        return None

    if 'interface' not in config:
        raise ConfigError('"interface" is required but not set!')

    if 'cpu' in config:
        if 'corelist_workers' in config['cpu'] and 'main_core' not in config[
                'cpu']:
            raise ConfigError('"cpu main-core" is required but not set!')

    memory_available: int = virtual_memory().available
    if memory_available < MIN_AVAILABLE_MEMORY:
        raise ConfigError(
            'Not enough free memory to start VPP:\n'
            f'available: {round(memory_available / 1024**3, 1)}GB\n'
            f'required: {round(MIN_AVAILABLE_MEMORY / 1024**3, 1)}GB')


def generate(config):
    if not config or (len(config) == 1 and 'removed_ifaces' in config):
        # Remove old config and return
        service_conf.unlink(missing_ok=True)
        return None

    render(service_conf, 'vpp/startup.conf.j2', config)
    render(systemd_override, 'vpp/override.conf.j2', config)

    # apply default sysctl values from
    # https://github.com/FDio/vpp/blob/v23.06/src/vpp/conf/80-vpp.conf
    sysctl_config: dict[str, str] = {
        'vm.nr_hugepages': '1024',
        'vm.max_map_count': '3096',
        'vm.hugetlb_shm_group': '0',
        'kernel.shmmax': '2147483648'
    }
    # we do not want to reduce `kernel.shmmax`
    kernel_shmnax_current: str = sysctl_read('kernel.shmmax')
    if int(kernel_shmnax_current) > int(sysctl_config['kernel.shmmax']):
        sysctl_config['kernel.shmmax'] = kernel_shmnax_current

    if not sysctl_apply(sysctl_config):
        raise ConfigError('Cannot configure sysctl parameters for VPP')

    return None


def apply(config):
    if not config or (len(config) == 1 and 'removed_ifaces' in config):
        call(f'systemctl stop {service_name}.service')
    else:
        call('systemctl daemon-reload')
        call(f'systemctl restart {service_name}.service')

    # Initialize interfaces removed from VPP
    for iface in config.get('removed_ifaces', []):
        host_control = HostControl()
        # rescan PCI to use a proper driver
        host_control.pci_rescan(iface['iface_pci_addr'])
        # rename to the proper name
        iface_new_name: str = host_control.get_eth_name(iface['iface_pci_addr'])
        host_control.rename_iface(iface_new_name, iface['iface_name'])

    if 'interface' in config:
        # connect to VPP
        # must be performed multiple attempts because API is not available
        # immediately after the service restart
        vpp_control = VPPControl(attempts=20, interval=500)
        for iface, _ in config['interface'].items():
            # Create lcp
            if iface not in Section.interfaces():
                vpp_control.lcp_pair_add(iface, iface)

    # reinitialize interfaces, but not during the first boot
    if boot_configuration_complete():
        call_dependents()


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
