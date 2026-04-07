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

import re
import json
import shutil
import ipaddress

from sys import exit
from time import sleep
from pathlib import Path

from vyos.config import Config
from vyos.utils.dict import dict_search
from vyos.utils.dict import dict_search_args
from vyos.utils.process import cmd
from vyos.utils.process import is_systemd_service_active
from vyos.utils.serial import send_command_to_iolan
from vyos.utils.serial import find_active_ttyS_devices
from vyos.utils.serial import print_global_change_warning
from vyos import ConfigError
from vyos.tpm import tpm_enabled
from vyos.tpm_pki import get_path_str
from vyos.tpm_pki import validate_certificate_against_tpm_priv_key

from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key

from vyos.configdict import node_changed
from vyos.configdict import is_node_changed

CERT_PATH = Path('/run/vyos_pki')
SERIAL_PATH = Path('/run/serial')
SERIAL_SERVICE = 'iolan-monitor.service'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['serial']

    proxy_no_default = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     no_tag_node_value_mangle=True,
                                     get_first_key=True,
                                     with_recursive_defaults=False)

    proxy = conf.get_config_dict(base, key_mangling=('-', '_'),
                                     no_tag_node_value_mangle=True,
                                     get_first_key=True,
                                     with_recursive_defaults=True,
                                     with_pki=True)
    if 'global' in proxy_no_default:
        if 'port_buffering' in proxy_no_default['global']:
            if 'syslog' in proxy_no_default['global']['port_buffering']:
                proxy['global']['port_buffering']['syslog_enable'] = '1'
            if 'local' in proxy_no_default['global']['port_buffering']:
                proxy['global']['port_buffering']['port_buffer_local'] = 1

        if 'tls' in proxy_no_default['global']:
            proxy['global']['tls'].update({'enabled': {}})
            if 'disable' in proxy_no_default['global'].get('tls', []):
                proxy['global']['tls'].update({'enabled': '0'})

    changed_tty_list = []
    for device in proxy.get('device', []):
        # Want to restart serial if its config changed
        tmp = is_node_changed(conf, base + ['device', device])
        # print(f'is_node_changed for {device}: {tmp}')
        if tmp:
            changed_tty_list.append(device)
            if 'tls' in proxy_no_default['device'][device]:
                proxy['device'][device]['tls'].update({'enabled': {}})
                if 'disable' in proxy_no_default['device'][device].get('tls', []):
                    proxy['device'][device]['tls'].update({'enabled': '0'})

    if changed_tty_list:
        proxy['serial_restart'] = changed_tty_list

    # print(f'changed_tty_list {changed_tty_list}')

    tmp = is_node_changed(conf, base + ['global'])
    if tmp:
        # print(f'global changed')
        proxy.update({'global_changed': tmp})

    # Delete serial port if was deleted from config tree
    tmp = node_changed(conf, base + ['device'])
    # print(f'serial_remove {tmp}')
    if tmp: proxy.update({'serial_remove': tmp})

    return proxy

def verify(proxy):
    if not proxy:
        return None

    if 'device' in proxy:
        for device, device_conf in proxy['device'].items():
            if dict_search('service', device_conf) == None:
                raise ConfigError('serial requires service parameter!')
            service = dict_search('service', device_conf)

            # TODO: need to differentiate server and and client mode, only server would need to listen
            listening_services = ['trueport-client', 'tcp-reverse', 'udp', 'vmodem', 'serial-tunnel']
            if service in listening_services:
                if dict_search('listen_port', device_conf) == None:
                    raise ConfigError(f'Service {service} requires listening port parameter!')

            outbound_multihost_service_mapping = {
                'trueport-server': 'trueport',
                'tcp-direct': 'direct',
            }
            if service in outbound_multihost_service_mapping:
                service_class = outbound_multihost_service_mapping.get(service)
                if dict_search('multihost.mode', device_conf['service_setting'][service_class]) == 'all-hosts':
                    if dict_search('multihost_list.host', device_conf) == None:
                        raise ConfigError(f'Must configure hostname and hostport in multihost-list for multihost mode all-hosts!')
                    for host_id, host_conf in dict_search('multihost_list.host', device_conf).items():
                        if (dict_search('name', device_conf['multihost_list']['host'][host_id]) == None
                            or dict_search('port', device_conf['multihost_list']['host'][host_id]) == None):
                            raise ConfigError(f'Must configure hostname and hostport in multihost-list for host {host_id}!')
                else:
                    if (dict_search('main_hostname', device_conf['service_setting'][service_class]) == None
                        or dict_search('main_hostport', device_conf['service_setting'][service_class]) == None):
                        raise ConfigError(f'Must configure main hostname and hostport for service {service}!')
                    if dict_search('multihost.mode', device_conf['service_setting'][service_class]) == 'backup-failover':
                        if (dict_search('multihost.backup_hostname', device_conf['service_setting'][service_class]) == None
                            or dict_search('multihost.backup_hostport', device_conf['service_setting'][service_class]) == None):
                            raise ConfigError(f'Must configure backup hostname and hostport for multihost mode backup-failover!')

            if 'tls' in device_conf:
                if 'enabled' in device_conf['tls']:
                    if device_conf['tls']['enabled'] != 0:
                        if 'certificate' not in device_conf['tls']:
                            raise ConfigError(f'Must configure certificate to enable tls on {device}!')
                        if tpm_enabled() and not validate_certificate_against_tpm_priv_key(get_path_str('cert', 'pem', device_conf['tls']['certificate']), get_path_str('cert', 'key', device_conf['tls']['certificate'])):
                            raise ConfigError(f'Configured certificate and key are invalid or do not match')

    return None

def replace_empty_dicts(d):
    if isinstance(d, dict):
        for key, value in d.items():
            if value == {}:
                d[key] = '1'
            elif isinstance(value, dict):
                replace_empty_dicts(value)
            elif isinstance(value, list):
                for item in value:
                    replace_empty_dicts(item)
    elif isinstance(d, list):
        for item in d:
            replace_empty_dicts(item)

def subtract_from_key(original_items):
    new_items = {}

    for key, value in original_items.items():
        new_key = str(int(key) - 1)  # subtract 1 and keep as string
        new_items[new_key] = value
    return new_items

def set_nested(d, keys, value):
    for key in keys[:-1]:
        d = d.setdefault(key, {})
    d[keys[-1]] = value

def generate(proxy):
    if not proxy:
        return None

    if 'device' in proxy:
        for device, serial_config in proxy['device'].items():
            port_config = serial_config
            ttynum = int(re.findall(r'\d+', device)[0])
            service = ''
            config_service = ''
            port_config['ttynum'] = ttynum

            if 'global' in proxy:
                port_config['global'] = proxy['global']
                if 'port_buffering' in port_config['global']:
                    local_enabled = 0
                    remote_enabled = 0
                    if 'port_buffer_local' in proxy['global']['port_buffering']:
                        local_enabled = 1
                    if 'nfs' in port_config['global']['port_buffering']:
                        if 'hostname' in port_config['global']['port_buffering']['nfs']:
                            port_config['global']['port_buffering']['port_buffer_remote'] = 1
                            remote_enabled = 1

                    if 'syslog_enable' in proxy['global']['port_buffering']:
                        local_enabled = 1
                        remote_enabled = 1

                    if local_enabled == 1 and remote_enabled == 1:
                        port_config['global']['port_buffering']['mode'] = 'both'
                    elif local_enabled == 1 and remote_enabled == 0:
                        port_config['global']['port_buffering']['mode'] = 'local'
                    elif local_enabled == 0 and remote_enabled == 1:
                        port_config['global']['port_buffering']['mode'] = 'remote'

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

                # reverse raw
                if 'tcp-reverse' in service:
                    if 'service_setting' in port_config:
                        if 'reverse' in port_config['service_setting']:
                            if 'allow_multiple_connection' in port_config['service_setting'].get('reverse', ''):
                                port_config['service'] = 'multihost'

                # direct & slient raw/ssh/telnet
                if 'tcp-direct' in service or 'ssh-direct' in service or 'telnet-direct' in service:
                    config_service = 'direct'
                    port_config['outbound'] = '1'
                    if 'service_setting' in port_config:
                        if 'direct' in port_config['service_setting']:
                            if 'tcp'in port_config['service_setting']['direct'] and 'tcp-direct' in service:
                                if 'multihost'in port_config['service_setting']['direct']['tcp']:
                                    multihost_mode = port_config['service_setting']['direct']['tcp']['multihost'].get('mode', '')
                                    if 'disable' not in multihost_mode:
                                        port_config['service'] = 'multihost'
                                        if 'backup' in multihost_mode:
                                            set_nested(port_config, ['multihost', 'mode'], 'backup-failover')
                            if port_config['service'] != 'multihost':
                                if (dict_search('service_setting.direct.initiate_any_char', port_config) == None
                                    and dict_search('service_setting.direct.initiate_specific_char', port_config) == None):
                                    port_config['service'] = service.rsplit('-', 1)[0] + '-' + 'slient'
                                else:
                                    if 'initiate_any_char' in port_config['service_setting']['direct']:
                                        port_config['raw_option'] = 'initiate-any-char'
                                    if 'initiate_specific_char' in port_config['service_setting']['direct']:
                                        port_config['raw_option'] = 'initiate-specific-char'
                                        port_config['direct_trigger'] = dict_search('service_setting.direct.initiate_specific_char', port_config)

                # modbus
                if 'modbus' in service:
                    if 'slave_mapping_list' in port_config['service_setting']['modbus']:
                        port_config['service_setting']['modbus']['slave_mapping_list'] = subtract_from_key(port_config['service_setting']['modbus']['slave_mapping_list'])
                        for key, value in port_config['service_setting']['modbus']['slave_mapping_list'].items():
                            if 'uid' in value:
                                if '-' in port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid']:
                                    uid_start, uid_end = map(int, port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid'].split('-'))
                                else:
                                    uid_start = uid_end = port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid']
                                port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid_start'] = uid_start
                                port_config['service_setting']['modbus']['slave_mapping_list'][key]['uid_end'] = uid_end

                # serial-tunnel
                if 'serial-tunnel' in service:
                    port_config['service'] = 'serial-tunnel-server'
                    if 'serial_tunnel' in port_config['service_setting']:
                        if port_config['service_setting']['serial_tunnel'].get('mode', '') == 'client':
                            port_config['service'] = 'serial-tunnel-client'

                # ppp
                if 'ppp' in service:
                    if 'local_address' in port_config['service_setting']['ppp']:
                        inet = ipaddress.IPv4Interface(port_config['service_setting']['ppp']['local_address'])
                        port_config['service_setting']['ppp']['v4_local_inet'] = str(inet.ip)
                        port_config['service_setting']['ppp']['v4_mask'] = str(inet.network.netmask)
                    if 'remote_address' in port_config['service_setting']['ppp']:
                        inet = ipaddress.IPv4Interface(port_config['service_setting']['ppp']['remote_address'])
                        port_config['service_setting']['ppp']['v4_remote_inet'] = str(inet.ip)
                        port_config['service_setting']['ppp']['v4_mask'] = str(inet.network.netmask)
                    if 'ipv6_global_network_prefix' in port_config['service_setting']['ppp']:
                        port_config['service_setting']['ppp']['v6_local_prefix'], port_config['service_setting']['ppp']['prefix_length'] = port_config['service_setting']['ppp']['ipv6_global_network_prefix'].split('/')

                # slip
                if 'slip' in service:
                    if 'local_address' in port_config['service_setting']['slip']:
                        inet = ipaddress.IPv4Interface(port_config['service_setting']['slip']['local_address'])
                        port_config['service_setting']['slip']['local_inet'] = str(inet.ip)
                        port_config['service_setting']['slip']['subnet_mask'] = str(inet.network.netmask)
                    if 'remote_address' in port_config['service_setting']['slip']:
                        inet = ipaddress.IPv4Interface(port_config['service_setting']['slip']['remote_address'])
                        port_config['service_setting']['slip']['remote_inet'] = str(inet.ip)
                        port_config['service_setting']['slip']['subnet_mask'] = str(inet.network.netmask)

            # multihost
            if port_config['service'] == 'multihost' and 'outbound' in port_config:
                if 'multihost_list' in port_config:
                    port_config['multihost_list']['host'] = subtract_from_key(port_config['multihost_list']['host'])
                if 'multihost' in port_config:
                    # these 2 keys are manually set, if 'multihost' exists 'mode' should exist
                    if port_config['multihost']['mode'] == 'backup-failover':
                        set_nested(port_config, ['multihost_list', 'host', '0', 'name'], dict_search('main_hostname', port_config['service_setting'][config_service]))
                        set_nested(port_config, ['multihost_list', 'host', '0', 'port'], dict_search('main_hostport', port_config['service_setting'][config_service]))
                        set_nested(port_config, ['multihost_list', 'host', '1', 'name'], dict_search('multihost.backup_hostname', port_config['service_setting'][config_service]))
                        set_nested(port_config, ['multihost_list', 'host', '1', 'port'], dict_search('multihost.backup_hostport', port_config['service_setting'][config_service]))

            # data-logging
            if 'data_logging' in port_config:
                if 'trueport' in service or 'tcp' in service:
                    # trueport inbound and outbound use the same service enum
                    if 'trueport' in service:
                        set_nested(port_config, ['datalogging', 'init_service'], 'trueport')
                    # direct/slient/reverse raw each has an enum
                    elif 'tcp' in service:
                        set_nested(port_config, ['datalogging', 'init_service'], service)

                    port_config['service'] = 'data-logging'
                    if 'outbound' in port_config:
                        set_nested(port_config, ['datalogging', 'hostname'], dict_search('main_hostname', port_config['service_setting'][config_service]))
                        set_nested(port_config, ['datalogging', 'port'], dict_search('main_hostport', port_config['service_setting'][config_service]))

            if 'hardware' in port_config:
                if 'rts_toggle' in port_config['hardware']:
                    port_config['hardware']['rts_toggle']['enabled'] = '1'

            tls_paths = []
            if 'tls' in port_config:
                tls_paths.append(port_config['tls'])
            if 'global' in port_config:
                if 'tls' in port_config['global']:
                    tls_paths.append(port_config['global']['tls'])
            for path in tls_paths:
                if 'peer_verification' in path:
                    if 'disable' not in path['peer_verification']:
                        path['verify_peer'] = 1

                if 'cipher_options' in path:
                    path['cipher_options'] = subtract_from_key(path['cipher_options'])

                cert_name = ''
                if 'certificate' in path and not tpm_enabled():
                    cert_name = path['certificate']

                    cert_data = dict_search_args(proxy['pki'], 'certificate', cert_name, 'certificate')
                    key_data = dict_search_args(proxy['pki'], 'certificate', cert_name, 'private', 'key')

                    CERT_PATH.mkdir(parents=True, exist_ok=True)
                    cert_file_path = (CERT_PATH/f'ssl_cert_{cert_name}.pem').absolute()
                    with cert_file_path.open('w') as f:
                        f.write(wrap_certificate(cert_data))

                    password_protected = 0
                    if 'passphrase' in path:
                        if 'password_protected' not in proxy['pki']['certificate'][cert_name]['private']:
                            path['passphrase'] = ''
                        else:
                            password_protected = 1

                    key_file_path = (CERT_PATH/f'ssl_key_{cert_name}.pem').absolute()
                    with key_file_path.open('w') as f:
                        f.write(wrap_private_key(key_data, password_protected))

            #inet
            if 'inet' in port_config:
                port_config['inet_configured'] = port_config['inet']
                del port_config['inet']
                if 'reverse' in port_config.get('service', ''):
                    if 'service_setting' in port_config:
                        if 'reverse' in port_config['service_setting']:
                            if 'ip_aliasing' in port_config['service_setting'].get('reverse', ''):
                                port_config['inet'] = port_config['inet_configured']

                if 'modbus' in port_config.get('service', ''):
                    if 'global' in port_config:
                        if 'modbus_gateway' in port_config['global']:
                            if 'ip_aliasing' in port_config['global'].get('modbus_gateway', ''):
                                port_config['inet'] = port_config['inet_configured']

            replace_empty_dicts(port_config)

            SERIAL_PATH.mkdir(parents=True, exist_ok=True)
            cfg_filename = (SERIAL_PATH/f'ttyS{ttynum}.json').absolute()
            with cfg_filename.open('w') as f:
                json.dump(port_config, f, indent=4)

    # print(proxy)
    return proxy

def apply(proxy):
    if not proxy or 'device' not in proxy:
        if is_systemd_service_active(SERIAL_SERVICE):
            cmd(f'systemctl stop {SERIAL_SERVICE}')
            shutil.rmtree(SERIAL_PATH)
        return None
    else:
        if not is_systemd_service_active(SERIAL_SERVICE):
            cmd(f'systemctl start {SERIAL_SERVICE}')
            cmd(f'systemctl is-active --wait {SERIAL_SERVICE}')

    if 'serial_remove' in proxy:
        for device in proxy['serial_remove']:
            send_command_to_iolan('delete', device)

    if 'device' in proxy:
        displayed_warning = 0
        for device, serial_config in proxy['device'].items():
            if 'serial_restart' in proxy:
                if 'global_changed' in proxy:
                    all_devices = find_active_ttyS_devices()
                    for item in all_devices:
                        if item not in proxy['serial_restart'] and displayed_warning == 0:
                            print_global_change_warning()
                            displayed_warning = 1
                if device not in proxy['serial_restart']:
                    continue
            else:
                if 'global_changed' in proxy:
                    print_global_change_warning()
                break

            while not is_systemd_service_active(SERIAL_SERVICE):
                sleep(0.100)

            if 'disable' not in serial_config:
                send_command_to_iolan('restart', device)
            else:
                send_command_to_iolan('stop', device)

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        modified = generate(c)
        apply(modified)
    except ConfigError as e:
        print(e)
        exit(1)
