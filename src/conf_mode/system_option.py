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
import psutil

from sys import exit
from time import sleep


from vyos.config import Config
from vyos.configverify import verify_source_interface
from vyos.configverify import verify_interface_exists
from vyos.system import grub_util
from vyos.template import render
from vyos.utils.cpu import get_cpus
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.kernel import check_kmod
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_running
from vyos.utils.network import is_addr_assigned
from vyos.utils.network import is_intf_addr_assigned
from vyos.utils.system import sysctl_write
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos import ConfigError
from vyos import airbag

from vyos.vpp.config_resource_checks import memory as mem_check

airbag.enable()

curlrc_config = r'/etc/curlrc'
ssh_config = r'/etc/ssh/ssh_config.d/91-vyos-ssh-client-options.conf'
systemd_action_file = '/lib/systemd/system/ctrl-alt-del.target'
usb_autosuspend = r'/etc/udev/rules.d/40-usb-autosuspend.rules'
kernel_dynamic_debug = r'/sys/kernel/debug/dynamic_debug/control'
time_format_to_locale = {'12-hour': 'en_US.UTF-8', '24-hour': 'en_GB.UTF-8'}
tuned_profiles = {
    'power-save': 'powersave',
    'network-latency': 'network-latency',
    'network-throughput': 'network-throughput',
    'virtual-guest': 'virtual-guest',
    'virtual-host': 'virtual-host',
}


def _get_total_hugepages_and_memory(config):
    unit_map = {'M': 1 << 20, 'G': 1 << 30}

    total_pages = 0
    total_bytes = 0

    hp_sizes = config.get('hugepage_size', {})
    for size_str, hp_config in hp_sizes.items():
        pages = int(hp_config.get('hugepage_count', 0))
        total_pages += pages
        total_bytes += pages * int(size_str[:-1]) * unit_map[size_str[-1]]

    return total_pages, total_bytes


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'option']
    options = conf.get_config_dict(
        base, key_mangling=('-', '_'), get_first_key=True, with_recursive_defaults=True
    )

    if 'performance' in options:
        # Update IPv4/IPv6 and sysctl options after tuned applied it's settings
        set_dependents('ip_ipv6', conf)
        set_dependents('sysctl', conf)

    return options


def verify(options):
    if 'http_client' in options:
        config = options['http_client']
        if 'source_interface' in config:
            verify_interface_exists(options, config['source_interface'])

        if {'source_address', 'source_interface'} <= set(config):
            raise ConfigError(
                'Can not define both HTTP source-interface and source-address'
            )

        if 'source_address' in config:
            if not is_addr_assigned(config['source_address']):
                raise ConfigError('No interface with given address specified!')

    if 'ssh_client' in options:
        config = options['ssh_client']
        if 'source_address' in config:
            address = config['source_address']
            if not is_addr_assigned(config['source_address']):
                raise ConfigError('No interface with address "{address}" configured!')

        if 'source_interface' in config:
            # verify_source_interface reuires key 'ifname'
            config['ifname'] = config['source_interface']
            verify_source_interface(config)
            if 'source_address' in config:
                address = config['source_address']
                interface = config['source_interface']
                if not is_intf_addr_assigned(interface, address):
                    raise ConfigError(
                        f'Address "{address}" not assigned on interface "{interface}"!'
                    )

    if 'kernel' in options:
        _cpu_info = get_cpus()[0]
        cpu_vendor = _cpu_info.get('vendor_id', 'unknown')
        if 'amd_pstate_driver' in options['kernel'] and cpu_vendor != 'AuthenticAMD':
            raise ConfigError(
                f'AMD pstate driver cannot be used with "{cpu_vendor}" CPU!'
            )

        _, hp_memory_bytes = _get_total_hugepages_and_memory(
            options['kernel'].get('memory', {})
        )
        if hp_memory_bytes:
            memory = psutil.virtual_memory()
            memory_total_bytes = memory.total

            # Exclude hugepage usage from system "used" memory
            hp_memory_used = sum(
                p['memory'] for p in mem_check.get_hugepages_info().values()
            )
            memory_used_bytes = memory.used - hp_memory_used

            # TODO: need to calculate how much memory is consumed for other services, tmpfs etc.
            # for now we should leave at least 4 GB for system usage and other processes
            min_system_reserved_gd = 4
            memory_margin_gb = 1
            reserved_bytes = max(
                min_system_reserved_gd * 1024**3,
                memory_used_bytes + memory_margin_gb * 1024**3,
            )

            available_for_hp_bytes = memory_total_bytes - reserved_bytes
            if available_for_hp_bytes < hp_memory_bytes:
                # For the error message, convert to GB and round to 1 decimal
                hp_memory_gb = round(hp_memory_bytes / 1024**3, 1)
                available_for_hp_gb = max(0, round(available_for_hp_bytes / 1024**3, 1))
                reserved_gb = round(reserved_bytes / 1024**3, 1)
                raise ConfigError(
                    f'Configured hugepages require {hp_memory_gb} GB of memory, but only '
                    f'{available_for_hp_gb:.1f} GB is available '
                    f'({reserved_gb} GB is reserved for system usage and services)'
                )

    return None


def generate(options):
    render(curlrc_config, 'system/curlrc.j2', options)
    render(ssh_config, 'system/ssh_config.j2', options)
    render(usb_autosuspend, 'system/40_usb_autosuspend.j2', options)

    # XXX: This code path and if statements must be kept in sync with the Kernel
    # option handling in image_installer.py:get_cli_kernel_options(). This
    # occurance is used for having the appropriate options passed to GRUB
    # when re-configuring options on the CLI.
    cmdline_options = []
    kernel_opts = options.get('kernel', {})
    k_cpu_opts = kernel_opts.get('cpu', {})
    k_memory_opts = kernel_opts.get('memory', {})
    if 'kernel' in options:
        if 'disable_mitigations' in options['kernel']:
            cmdline_options.append('mitigations=off')
        if 'disable_power_saving' in options['kernel']:
            cmdline_options.append('intel_idle.max_cstate=0 processor.max_cstate=1')
        if 'amd_pstate_driver' in options['kernel']:
            mode = options['kernel']['amd_pstate_driver']
            cmdline_options.append(
                f'initcall_blacklist=acpi_cpufreq_init amd_pstate={mode}')
        if 'quiet' in options['kernel']:
            cmdline_options.append('quiet')

    if 'disable_hpet' in kernel_opts:
        cmdline_options.append('hpet=disable')

    if 'disable_mce' in kernel_opts:
        cmdline_options.append('mce=off')

    if 'disable_softlockup' in kernel_opts:
        cmdline_options.append('nosoftlockup')

    # CPU options
    isol_cpus = k_cpu_opts.get('isolate_cpus')
    if isol_cpus:
        cmdline_options.append(f'isolcpus={isol_cpus}')

    nohz_full = k_cpu_opts.get('nohz_full')
    if nohz_full:
        cmdline_options.append(f'nohz_full={nohz_full}')

    rcu_nocbs = k_cpu_opts.get('rcu_no_cbs')
    if rcu_nocbs:
        cmdline_options.append(f'rcu_nocbs={rcu_nocbs}')

    if 'disable_nmi_watchdog' in k_cpu_opts:
        cmdline_options.append('nmi_watchdog=0')

    # Memory options
    if 'disable_numa_balancing' in k_memory_opts:
        cmdline_options.append('numa_balancing=disable')

    default_hp_size = k_memory_opts.get('default_hugepage_size')
    if default_hp_size:
        cmdline_options.append(f'default_hugepagesz={default_hp_size}')

    hp_sizes = k_memory_opts.get('hugepage_size')
    if hp_sizes:
        for size, settings in hp_sizes.items():
            cmdline_options.append(f'hugepagesz={size}')
            count = settings.get('hugepage_count')
            if count:
                cmdline_options.append(f'hugepages={count}')

    grub_util.update_kernel_cmdline_options(' '.join(cmdline_options))

    return None


def apply(options):
    # System bootup beep
    beep_service = 'vyos-beep.service'
    if 'startup_beep' in options:
        cmd(f'systemctl enable {beep_service}')
    else:
        cmd(f'systemctl disable {beep_service}')

    # Ctrl-Alt-Delete action
    if os.path.exists(systemd_action_file):
        os.unlink(systemd_action_file)
    if 'ctrl_alt_delete' in options:
        if options['ctrl_alt_delete'] == 'reboot':
            os.symlink('/lib/systemd/system/reboot.target', systemd_action_file)
        elif options['ctrl_alt_delete'] == 'poweroff':
            os.symlink('/lib/systemd/system/poweroff.target', systemd_action_file)

    # Configure HTTP client
    if 'http_client' not in options:
        if os.path.exists(curlrc_config):
            os.unlink(curlrc_config)

    # Configure SSH client
    if 'ssh_client' not in options:
        if os.path.exists(ssh_config):
            os.unlink(ssh_config)

    # Reboot system on kernel panic
    timeout = '0'
    if 'reboot_on_panic' in options:
        timeout = '60'
    with open('/proc/sys/kernel/panic', 'w') as f:
        f.write(timeout)

    # tuned - performance tuning
    if 'performance' in options:
        cmd('systemctl restart tuned.service')
        # wait until daemon has started before sending configuration
        while not is_systemd_service_running('tuned.service'):
            sleep(0.250)
        performance = ' '.join(
            list(tuned_profiles[profile] for profile in options['performance'])
        )
        cmd(f'tuned-adm profile {performance}')
    else:
        cmd('systemctl stop tuned.service')

    call_dependents()

    # Keyboard layout - there will be always the default key inside the dict
    # but we check for key existence anyway
    if 'keyboard_layout' in options:
        cmd('loadkeys {keyboard_layout}'.format(**options))

    # Enable/diable root-partition-auto-resize SystemD service
    if 'root_partition_auto_resize' in options:
        cmd('systemctl enable root-partition-auto-resize.service')
    else:
        cmd('systemctl disable root-partition-auto-resize.service')

    # Time format 12|24-hour
    if 'time_format' in options:
        time_format = time_format_to_locale.get(options['time_format'])
        cmd(f'localectl set-locale LC_TIME={time_format}')

    # Reload UDEV, required for USB auto suspend
    cmd('udevadm control --reload-rules')

    # Enable/disable dynamic debugging for kernel modules
    modules = ['wireguard']
    modules_enabled = dict_search('kernel.debug', options) or []
    for module in modules:
        if module in modules_enabled:
            check_kmod(module)
            write_file(kernel_dynamic_debug, f'module {module} +p')
        else:
            write_file(kernel_dynamic_debug, f'module {module} -p')

    if 'resource_limits' in options:
        total_pages, total_bytes = _get_total_hugepages_and_memory(
            options.get('kernel', {}).get('memory', {})
        )

        # Minimum recommended system values
        max_map_count_min = 65530  # ensures large workload compatibility
        shmmax_min = 8589934592  # 8 GiB safe default for large allocations

        max_map_count_conf = options['resource_limits'].get('max_map_count', 'auto')
        shmmax_conf = options['resource_limits'].get('shmmax', 'auto')

        parameters = {
            'vm.max_map_count': (
                max(total_pages * 2, max_map_count_min)
                if max_map_count_conf == 'auto'
                else int(max_map_count_conf)
            ),
            'kernel.shmmax': (
                max(total_bytes, shmmax_min)
                if shmmax_conf == 'auto'
                else int(shmmax_conf)
            ),
        }

        for parameter, value in parameters.items():
            sysctl_write(parameter, value)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
