#!/usr/bin/env python3
#
# Copyright (C) 2018-2025 VyOS maintainers and contributors
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
import re
import sys
import json
import signal
import subprocess

from sys import exit
from psutil import process_iter
from collections import defaultdict

from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.process import cmd
from vyos import ConfigError

from vyos.configdict import node_changed
from vyos.configdict import is_node_changed
# from vyos.configdiff import get_config_diff, Diff

def ensure_folder_exists(path):
    if not os.path.exists(path):
        os.makedirs(path)
    #     print(f'Folder created: {path}')
    # else:
    #     print(f'Folder already exists: {path}')

def replace_empty_dicts(d):
    if isinstance(d, dict):
        for key, value in d.items():
            if value == {}:
                print(f'key empty value is {key}')
                d[key] = '1'
            elif isinstance(value, dict):
                replace_empty_dicts(value)
            elif isinstance(value, list):
                for item in value:
                    replace_empty_dicts(item)
    elif isinstance(d, list):
        for item in d:
            replace_empty_dicts(item)

def kill_pid_file(tty, is_modbus):
    if is_modbus:
        pid_suffix = f'smodbusd.pid'
    else:
        pid_suffix = f'{tty}.pid'
    base_dir = '/run/serial'

    try:
        for filename in os.listdir(base_dir):
            if not filename.endswith(pid_suffix):
                continue

            file_path = os.path.join(base_dir, filename)

            try:
                with open(file_path, 'r') as pid_file:
                    pid_str = pid_file.read().strip()
                    if not pid_str.isdigit():
                        print(f'Invalid PID in file {file_path}: {pid_str}')
                        continue

                    pid = int(pid_str)
                    os.kill(pid, signal.SIGTERM)
                    print(f'Successfully killed PID {pid} from {file_path}')

            except ProcessLookupError:
                print(f'No such process with PID in {file_path}, ignore')
            except PermissionError:
                print(f'Permission denied when trying to kill PID from {file_path}')
            except Exception as e:
                print(f'An error occurred while handling {file_path}: {e}')
    except FileNotFoundError:
        print(f'Directory {base_dir} does not exist')
    except Exception as e:
        print(f'Error accessing {base_dir}: {e}')

def subtract_from_key(original_items):
    new_items = {}

    for key, value in original_items.items():
        new_key = str(int(key) - 1)  # subtract 1 and keep as string
        new_items[new_key] = value
    return new_items

def get_values_by_key(data, target_key):
    results = []

    if isinstance(data, dict):
        for key, value in data.items():
            if key == target_key:
                results.append(value)
            # Search deeper
            results.extend(get_values_by_key(value, target_key))

    elif isinstance(data, list):
        for item in data:
            results.extend(get_values_by_key(item, target_key))

    return results

def set_nested(d, keys, value):
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['serial']

    # Retrieve CLI representation as dictionary
    # proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
    #                              get_first_key=True)

    proxy_no_default = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     no_tag_node_value_mangle=True,
                                     get_first_key=True,
                                     with_recursive_defaults=False)

    proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     no_tag_node_value_mangle=True,
                                     get_first_key=True,
                                     with_recursive_defaults=True)
    # if 'global' in proxy:
    tmp = is_node_changed(conf, base + ['global', 'modbus-gateway'])
    print(f'is modbus gateway changed {tmp}')
    if tmp:
        if 'ip_aliasing' not in proxy['global']['modbus_gateway']:
            print('should restart smodbusd_restart')
            proxy['smodbusd_restart'] = '1'

    for device in proxy.get('device', []):
        # Want to restart serial if its config changed
        tmp = is_node_changed(conf, base + ['device', device])
        print(tmp)
        if tmp:
            proxy['serial_restart'] = [device]

    # Delete serial port if was deleted from config tree
    tmp = node_changed(conf, base + ['device'])
    print(tmp)
    if tmp: proxy.update({'serial_remove': tmp})

    if 'device' in proxy:
        for device, serial_config in proxy['device'].items():
            port_config = serial_config
            ttynum = re.findall(r'\d+', device)[0]
            service = ''
            config_service = ''
            port_config['ttynum'] = ttynum

            if 'global' in proxy:
                port_config['global'] = proxy.pop('global')

            if 'service' in port_config:
                service = port_config.get('service', '')
                # trueport
                if 'trueport' in service:
                    port_config['service'] = 'trueport'
                    config_service = 'trueport'
                    if 'server' in service:
                        port_config['outbound'] = '1'
                        port_config['service_setting']['trueport']['mode'] = 'server-initiate'
                        # server mode requires main hostname and port to be set under service_setting
                        if 'multihost' in port_config['service_setting']['trueport']:
                            multihost_mode = port_config['service_setting']['trueport']['multihost'].get('mode', '')
                            if 'disable' not in multihost_mode:
                                port_config['service'] = 'multihost'
                                if 'backup' in multihost_mode:
                                    set_nested(port_config, ['multihost', 'mode'], 'backup-failover')
                    else:
                        # client mode need to check if path service_setting exists
                        if 'service_setting' in port_config:
                            if 'trueport' in port_config['service_setting']:
                                if 'allow_multiple_connection' in port_config['service_setting'].get('trueport', ''):
                                    port_config['service'] = 'multihost'

                # vmodem
                if 'vmodem' in service:
                    if 'global' in port_config:
                        if 'vmodem_phone_list' in port_config['global']:
                            if 'entry' in port_config['global']['vmodem_phone_list']:
                                port_config['global']['vmodem_phone_list']['entry'] = subtract_from_key(port_config['global']['vmodem_phone_list']['entry'])
                    # vmodem would require service-setting to be set, skip checking if path exist for now
                    if 'send_connect_status' in port_config['service_setting']['vmodem']:
                        vmodem_style = port_config['service_setting']['vmodem'].get('send_connect_status', '')
                        if vmodem_style == 'disable':
                            set_nested(port_config, ['service_setting', 'vmodem', 'suppress'], '1')

                # udp
                if 'udp' in service:
                    if 'entry' in port_config['service_setting']['udp']:
                        port_config['service_setting']['udp']['entry'] = subtract_from_key(port_config['service_setting']['udp']['entry'])
                        for key, value in port_config['service_setting']['udp']['entry'].items():
                            if 'disable' in value:
                                # This path should be a required field, skip checking if path exists
                                port_config['service_setting']['udp']['entry'][key]['direction'] = 'disable'
                            if 'udp_port' in value:
                                if port_config['service_setting']['udp']['entry'][key]['udp_port'].isnumeric():
                                    port_config['service_setting']['udp']['entry'][key]['outbound_port'] = port_config['service_setting']['udp']['entry'][key]['udp_port']

                # modbus
                if 'modbus' in service:
                    if 'slave_mapping_list' in port_config['service_setting']['modbus']:
                        port_config['service_setting']['modbus']['slave_mapping_list'] = subtract_from_key(port_config['service_setting']['modbus']['slave_mapping_list'])
                        for key, value in port_config['service_setting']['modbus']['slave_mapping_list'].items():
                            if 'uid_range' in value:
                                uid_start, uid_end = map(int, port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid_range'].split('-'))
                                port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid_start'] = uid_start
                                port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid_end'] = uid_end

            # multihost
            if port_config['service'] == 'multihost':
                if 'multihost_list' in port_config:
                    port_config['multihost_list']['host'] = subtract_from_key(port_config['multihost_list']['host'])
                if 'multihost' in port_config:
                    # these 2 keys are manually set, if 'multihost' exists 'mode' should exist
                    if port_config['multihost']['mode'] == 'backup-failover':
                        set_nested(port_config, ['multihost_list', 'host', '0', 'name'], get_values_by_key(port_config['service_setting'][config_service], 'main_hostname')[0])
                        set_nested(port_config, ['multihost_list', 'host', '0', 'port'], get_values_by_key(port_config['service_setting'][config_service], 'main_hostport')[0])
                        set_nested(port_config, ['multihost_list', 'host', '1', 'name'], get_values_by_key(port_config['service_setting'][config_service], 'backup_hostname')[0])
                        set_nested(port_config, ['multihost_list', 'host', '1', 'port'], get_values_by_key(port_config['service_setting'][config_service], 'backup_hostport')[0])

            # data-logging
            if 'data_logging' in port_config:
                # trueport inbound and outbound use the same service enum
                if 'trueport' in service:
                    set_nested(port_config, ['datalogging', 'init_service'], 'trueport')
                # direct/slient/reverse raw each has an enum
                elif 'raw' in service:
                    set_nested(port_config, ['datalogging', 'init_service'], service)

                port_config['service'] = 'data-logging'
                if 'outbound' in port_config:
                    set_nested(port_config, ['datalogging', 'hostname'], get_values_by_key(port_config['service_setting'][config_service], 'main_hostname')[0])
                    set_nested(port_config, ['datalogging', 'port'], get_values_by_key(port_config['service_setting'][config_service], 'main_hostport')[0])

            if 'hardware' in port_config:
                if 'rts_toggle' in port_config['hardware']:
                    port_config['hardware']['rts_toggle']['enabled'] = '1'

            if 'tls' in proxy_no_default['device'][device]:
                if 'disable' not in proxy_no_default['device'][device].get('tls', []):
                    port_config['tls']['enabled'] = '1'

            replace_empty_dicts(port_config)

            ensure_folder_exists('/run/serial')
            filename = f'/run/serial/ttyS{ttynum}.json'
            with open(filename, 'w') as f:
                json.dump(port_config, f, indent=4)

    print(proxy)
    return proxy

def verify(proxy):
    if not proxy:
        return None
    return None

def generate(proxy):
    if not proxy:
        return None
    return None

def write_string_to_file(filename, content):
    try:
        with open(filename, 'w') as f:
            f.write(content)
        print(f'{content} written to {filename}')
    except Exception as e:
        print(f'Failed to write to {filename}: {e}')

def stop_services_and_remove_files_with_prefix(base_dir, prefix, stop):
    filelist = []
    for filename in os.listdir(base_dir):
        if filename.startswith(prefix):
            filepath = os.path.join(base_dir, filename)
            try:
                if stop:
                    if filename.endswith('.socket'):
                        cmd(f'systemctl stop {filename}')
                os.remove(filepath)
                filelist.append(filename)
                print(f'Removed: {filepath}')
            except Exception as e:
                print(f'Failed to remove {filepath}: {e}')
    if not filelist:
        print(f'No files starting with "{prefix}" found in {base_dir}.')
    else:
        return 1

def generate_systemd_socket_file(service, port, output_dir='/etc/systemd/system'):
    """
    Create a systemd socket unit that listens on a specified port
    When a connection is received, systemd activates and runs the associated service unit with the same name

    Used with reverse raw, reverse ssh, reverse telnet, and serial tunnelling
    """

    socket_file_name = f'iol_{service}_{port}.socket'
    filename = os.path.join(output_dir, socket_file_name)

    content = f'''
[Unit]
Description=Socket listener on port {port} for on-demand activation of service {service}

[Socket]
ListenStream={port}
Accept=yes

[Install]
WantedBy=sockets.target
'''
    ret = 0
    try:
        with open(filename, 'w') as f:
            f.write(content)
        try:
            result = subprocess.run(
                ['systemctl', 'is-enabled', socket_file_name],
                check=True,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True
            )
            status = result.stdout.strip()
        except subprocess.CalledProcessError as e:
            status = e.stdout.strip() or e.stderr.strip()
            print(f'Error checking enable status: {status}')

        if (status == 'masked'):
            os.system(f'systemctl unmask {socket_file_name}')
        os.system(f'systemctl enable {socket_file_name}')
        os.system(f'systemctl start {socket_file_name}')
        ret = 1
        print(f'Socket file written to: {filename}')
    except Exception as e:
        print(f'Error writing systemd socket file: {e}')
    return ret

def generate_systemd_service_file(service, exe, port, args, output_dir='/etc/systemd/system'):
    """
    Create a systemd service unit for socket activation
    When a connection is received on the matching socket unit,
    this service will be triggered to launch the specified executable

    Used with reverse raw, reverse ssh, reverse telnet, and serial tunnelling
    """

    socket_file_name = f'iol_{service}_{port}@.service'
    filename = os.path.join(output_dir, socket_file_name)

    content = f'''
[Unit]
Description=Service started on incoming connection to TCP port {port}

[Service]
ExecStart={exe} {args}

StandardInput=socket
'''

    ret = 0
    try:
        with open(filename, 'w') as f:
            f.write(content)
            ret = 1
        print(f'Service file written to: {filename}')
    except Exception as e:
        print(f'Error writing systemd service file: {e}')
    return ret

def group_serial_ports_by_tcp_port_for_rev_raw():
    """
    For hunt group
    Scan /run/serial for ttySx.json files
    For each file, if 'service' == 'tcp-reverse', group the 'ttySx' part in filename by 'listen_port' value
    Write output to <listen_port>_tcprvraw files in the same dir with ttySx list
    """

    base_dir = '/run/serial'

    removed_rev_list = []
    for filename in os.listdir(base_dir):
        if filename.endswith('_tcprvraw'):
            filepath = os.path.join(base_dir, filename)
            try:
                os.remove(filepath)
                removed_rev_list.append(filename)
                print(f'Removed: {filepath}')
            except Exception as e:
                print(f'Failed to remove {filepath}: {e}')
    if not removed_rev_list:
        print(f'No files ending with "_tcprvraw" found in {base_dir}.')

    groups = defaultdict(list)
    service = 'default'
    for fname in os.listdir(base_dir):
        if not fname.startswith('ttyS') or not fname.endswith('.json'):
            continue

        path = os.path.join(base_dir, fname)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if 'disable' in data:
                print(f'tty port with {path} shows disabled')
                continue
            if data.get('service') == 'tcp-reverse':
                service = data.get('service')
                tty = fname[:-5]
                listen_port = data.get('listen_port')
                if listen_port:
                    groups[listen_port].append(tty)
        except Exception as e:
            print(f'Error processing {path}: {e}')

    add_to_systemd = 0
    for listen_port, ttys in groups.items():
        if ttys:
            sorted_ttys = sorted(ttys, key=lambda x: int(x[4:])) # sort ttyS names by their numeric suffix
            out_file = os.path.join(base_dir, f'{listen_port}_tcprvraw')
            try:
                with open(out_file, 'w') as f:
                    f.write(', '.join(sorted_ttys) + '\n')

                if service == 'tcp-reverse':
                    add_service = generate_systemd_service_file('revraw', '/usr/bin/iol_revraw_pmgr', listen_port, listen_port)
                    add_socket = generate_systemd_socket_file('revraw', listen_port)

                if add_socket and add_service:
                    add_to_systemd = 1
                else:
                    print(f'Error creating systemd files')
                    sys.exit(2)
            except Exception as e:
                print(f'Error writing to {out_file}: {e}')

    return add_to_systemd

def check_any_running_service_modbus():
    """
    For smodbusd
    Scan /run/serial for ttySx.json files
    If found a config file which has 'service' == 'modbus-y'
    return x
    """

    base_dir = '/run/serial'

    for fname in os.listdir(base_dir):
        if not fname.startswith('ttyS') or not fname.endswith('.json'):
            continue

        path = os.path.join(base_dir, fname)
        try:
            with open(path, 'r') as f:
                data = json.load(f)
            if 'disable' in data:
                print(f'tty port with {path} shows disabled')
                continue
            if 'modbus' in data.get('service'):
                return re.findall(r'\d+', fname)[0]
        except Exception as e:
            print(f'Error processing {path}: {e}')

def is_pid_running(pid):
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False

def restart_smodbusd(tty):
    print(f'Restarting service iol_smodbusd...')
    ret = os.system(f'setsid iol_smodbusd -P {tty} &')
    print(f'iol_smodbusd ret {ret}')

def apply(proxy):
    if not proxy:
        return None

    if 'serial_remove' in proxy:
        for device in proxy['serial_remove']:
            stop_services_and_remove_files_with_prefix('/run/serial', device, False)
            kill_pid_file(device, 0)

    if 'serial_restart' in proxy:
        for device in proxy['serial_restart']:
            kill_pid_file(device, 0)

    if 'smodbusd_restart' in proxy:
        kill_pid_file('', 1)

    tty = check_any_running_service_modbus()
    if (tty):
        smodbusd_pid_file = '/run/serial/smodbusd.pid'
        if os.path.exists(smodbusd_pid_file):
            try:
                with open(smodbusd_pid_file, 'r') as f:
                    pid = int(f.read().strip())
                if not is_pid_running(pid):
                    print(f'iol_smodbusd pid {pid} not running.')
                    restart_smodbusd(tty)
                else:
                    print(f'iol_smodbusd pid {pid} is running.')
            except Exception as e:
                print(f'Error reading iol_smodbusd pid or checking status: {e}')
                restart_smodbusd(tty)
        else:
            print(f'iol_smodbusd pid file {smodbusd_pid_file} not found.')
            restart_smodbusd(tty)

    add_to_systemd = 0
    remove_from_systemd = 0

    remove_from_systemd = stop_services_and_remove_files_with_prefix('/etc/systemd/system', 'iol_', True)
    add_to_systemd = group_serial_ports_by_tcp_port_for_rev_raw()

    if add_to_systemd or remove_from_systemd:
        call('systemctl daemon-reload')

    if 'device' in proxy:
        ret = 0
        for device, serial_config in proxy['device'].items():
            ttynum = re.findall(r'\d+', device)[0]
            if 'disable' not in serial_config:
                file_path = f'/run/serial/{device}.exe'

                if 'trueport' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_vc')
                    ret = os.system(f'setsid iol_monitor {ttynum} &')
                    print(f'vc monitor ret {ret}')
                elif 'multihost' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_multihost')

                    if 'outbound' in serial_config:
                        # outbound will keep running
                        ret = os.system(f'setsid iol_multihost {ttynum} &')
                        print(f'iol_multihost ret {ret}')
                    else:
                        # inbound will exit when all connections disconnect
                        ret = os.system(f'setsid iol_monitor {ttynum} &')
                        print(f'iol_multihost monitor ret {ret}')
                elif 'data-logging' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_lldatalog')
                    ret = os.system(f'setsid iol_monitor {ttynum} &')
                    print(f'data-logging monitor ret {ret}')
                elif 'vmodem' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_vmodem')
                    vmodem_mode = serial_config['service_setting']['vmodem'].get('mode', '')
                    if vmodem_mode == 'manual':
                        listen_port = serial_config['listen_port']
                        ret = os.system(f'setsid iol_monitor {ttynum} {listen_port} &')
                    else:
                        ret = os.system(f'setsid iol_monitor {ttynum} &')
                    print(f'vmodem monitor ret {ret}')
                elif 'udp' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_udpd')
                    ret = os.system(f'setsid iol_udpd {ttynum} &')
                    print(f'iol_udpd ret {ret}')
                elif 'tcp-reverse' in serial_config['service']:
                    write_string_to_file(file_path, '')
                    print(f'running tcp-reverse on {device}')
                elif 'modbus-master' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_mmodbusp')
                    ret = os.system(f'setsid iol_mmodbusp -p {ttynum} &')
                    print(f'iol_mmodbusp ret {ret}')
                elif 'modbus-slave' in serial_config['service']:
                    write_string_to_file(file_path, 'iol_smodbusp')
                    ret = os.system(f'setsid iol_smodbusp -P {ttynum} &')
                    print(f'iol_smodbusp ret {ret}')
            else:
                kill_pid_file(device, 0)

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
