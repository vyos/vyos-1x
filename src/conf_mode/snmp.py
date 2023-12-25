#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
from vyos.configdict import dict_merge
from vyos.configverify import verify_vrf
from vyos.snmpv3_hashgen import plaintext_to_md5
from vyos.snmpv3_hashgen import plaintext_to_sha1
from vyos.snmpv3_hashgen import random
from vyos.template import render
from vyos.utils.process import call
from vyos.utils.permission import chmod_755
from vyos.utils.dict import dict_search
from vyos.utils.network import is_addr_assigned
from vyos.version import get_version_data
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file_client  = r'/etc/snmp/snmp.conf'
config_file_daemon  = r'/etc/snmp/snmpd.conf'
config_file_access  = r'/usr/share/snmp/snmpd.conf'
config_file_user    = r'/var/lib/snmp/snmpd.conf'
systemd_override    = r'/run/systemd/system/snmpd.service.d/override.conf'
systemd_service     = 'snmpd.service'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'snmp']

    snmp = conf.get_config_dict(base, key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)
    if not conf.exists(base):
        snmp.update({'deleted' : ''})

    if conf.exists(['service', 'lldp', 'snmp']):
        snmp.update({'lldp_snmp' : ''})

    if 'deleted' in snmp:
        return snmp

    version_data = get_version_data()
    snmp['version'] = version_data['version']

    # create an internal snmpv3 user of the form 'vyosxxxxxxxxxxxxxxxx'
    snmp['vyos_user'] = 'vyos' + random(8)
    snmp['vyos_user_pass'] = random(16)

    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    snmp = conf.merge_defaults(snmp, recursive=True)

    if 'listen_address' in snmp:
        # Always listen on localhost if an explicit address has been configured
        # This is a safety measure to not end up with invalid listen addresses
        # that are not configured on this system. See https://vyos.dev/T850
        if '127.0.0.1' not in snmp['listen_address']:
            tmp = {'127.0.0.1': {'port': '161'}}
            snmp['listen_address'] = dict_merge(tmp, snmp['listen_address'])

        if '::1' not in snmp['listen_address']:
            tmp = {'::1': {'port': '161'}}
            snmp['listen_address'] = dict_merge(tmp, snmp['listen_address'])

    return snmp

def verify(snmp):
    if 'deleted' in snmp:
        return None

    if {'deleted', 'lldp_snmp'} <= set(snmp):
        raise ConfigError('Can not delete SNMP service, as LLDP still uses SNMP!')

    ### check if the configured script actually exist
    if 'script_extensions' in snmp and 'extension_name' in snmp['script_extensions']:
        for extension, extension_opt in snmp['script_extensions']['extension_name'].items():
            if 'script' not in extension_opt:
                raise ConfigError(f'Script extension "{extension}" requires an actual script to be configured!')

            tmp = extension_opt['script']
            if not os.path.isfile(tmp):
                Warning(f'script "{tmp}" does not exist!')
            else:
                chmod_755(extension_opt['script'])

    if 'listen_address' in snmp:
        for address in snmp['listen_address']:
            # We only wan't to configure addresses that exist on the system.
            # Hint the user if they don't exist
            if 'vrf' in snmp:
                vrf_name = snmp['vrf']
                if not is_addr_assigned(address, vrf_name) and address not in ['::1','127.0.0.1']:
                    raise ConfigError(f'SNMP listen address "{address}" not configured in vrf "{vrf_name}"!')
            elif not is_addr_assigned(address):
                raise ConfigError(f'SNMP listen address "{address}" not configured in default vrf!')

    if 'trap_target' in snmp:
        for trap, trap_config in snmp['trap_target'].items():
            if 'community' not in trap_config:
                raise ConfigError(f'Trap target "{trap}" requires a community to be set!')

    if 'oid_enable' in snmp:
        Warning(f'Custom OIDs are enabled and may lead to system instability and high resource consumption')


    verify_vrf(snmp)

    # bail out early if SNMP v3 is not configured
    if 'v3' not in snmp:
        return None

    if 'user' in snmp['v3']:
        for user, user_config in snmp['v3']['user'].items():
            if 'group' not in user_config:
                raise ConfigError(f'Group membership required for user "{user}"!')

            if 'plaintext_password' not in user_config['auth'] and 'encrypted_password' not in user_config['auth']:
                raise ConfigError(f'Must specify authentication encrypted-password or plaintext-password for user "{user}"!')

            if 'plaintext_password' not in user_config['privacy'] and 'encrypted_password' not in user_config['privacy']:
                raise ConfigError(f'Must specify privacy encrypted-password or plaintext-password for user "{user}"!')

    if 'group' in snmp['v3']:
        for group, group_config in snmp['v3']['group'].items():
            if 'seclevel' not in group_config:
                raise ConfigError(f'Must configure "seclevel" for group "{group}"!')
            if 'view' not in group_config:
                raise ConfigError(f'Must configure "view" for group "{group}"!')

            # Check if 'view' exists
            view = group_config['view']
            if 'view' not in snmp['v3'] or view not in snmp['v3']['view']:
                raise ConfigError(f'You must create view "{view}" first!')

    if 'view' in snmp['v3']:
        for view, view_config in snmp['v3']['view'].items():
            if 'oid' not in view_config:
                raise ConfigError(f'Must configure an "oid" for view "{view}"!')

    if 'trap_target' in snmp['v3']:
        for trap, trap_config in snmp['v3']['trap_target'].items():
            if 'plaintext_password' not in trap_config['auth'] and 'encrypted_password' not in trap_config['auth']:
                raise ConfigError(f'Must specify one of authentication encrypted-password or plaintext-password for trap "{trap}"!')

            if {'plaintext_password', 'encrypted_password'} <= set(trap_config['auth']):
                raise ConfigError(f'Can not specify both authentication encrypted-password and plaintext-password for trap "{trap}"!')

            if 'plaintext_password' not in trap_config['privacy'] and 'encrypted_password' not in trap_config['privacy']:
                raise ConfigError(f'Must specify one of privacy encrypted-password or plaintext-password for trap "{trap}"!')

            if {'plaintext_password', 'encrypted_password'} <= set(trap_config['privacy']):
                raise ConfigError(f'Can not specify both privacy encrypted-password and plaintext-password for trap "{trap}"!')

            if 'type' not in trap_config:
                raise ConfigError('SNMP v3 trap "type" must be specified!')

    return None

def generate(snmp):
    # As we are manipulating the snmpd user database we have to stop it first!
    # This is even save if service is going to be removed
    call(f'systemctl stop {systemd_service}')
    # Clean config files
    config_files = [config_file_client, config_file_daemon,
                    config_file_access, config_file_user, systemd_override]
    for file in config_files:
        if os.path.isfile(file):
            os.unlink(file)

    if 'deleted' in snmp:
        return None

    if 'v3' in snmp:
        # net-snmp is now regenerating the configuration file in the background
        # thus we need to re-open and re-read the file as the content changed.
        # After that we can no read the encrypted password from the config and
        # replace the CLI plaintext password with its encrypted version.
        os.environ['vyos_libexec_dir'] = '/usr/libexec/vyos'

        if 'user' in snmp['v3']:
            for user, user_config in snmp['v3']['user'].items():
                if dict_search('auth.type', user_config)  == 'sha':
                    hash = plaintext_to_sha1
                else:
                    hash = plaintext_to_md5

                if dict_search('auth.plaintext_password', user_config) is not None:
                    tmp = hash(dict_search('auth.plaintext_password', user_config),
                        dict_search('v3.engineid', snmp))

                    snmp['v3']['user'][user]['auth']['encrypted_password'] = tmp
                    del snmp['v3']['user'][user]['auth']['plaintext_password']

                    call(f'/opt/vyatta/sbin/my_set service snmp v3 user "{user}" auth encrypted-password "{tmp}" > /dev/null')
                    call(f'/opt/vyatta/sbin/my_delete service snmp v3 user "{user}" auth plaintext-password > /dev/null')

                if dict_search('privacy.plaintext_password', user_config) is not None:
                    tmp = hash(dict_search('privacy.plaintext_password', user_config),
                        dict_search('v3.engineid', snmp))

                    snmp['v3']['user'][user]['privacy']['encrypted_password'] = tmp
                    del snmp['v3']['user'][user]['privacy']['plaintext_password']

                    call(f'/opt/vyatta/sbin/my_set service snmp v3 user "{user}" privacy encrypted-password "{tmp}" > /dev/null')
                    call(f'/opt/vyatta/sbin/my_delete service snmp v3 user "{user}" privacy plaintext-password > /dev/null')

    # Write client config file
    render(config_file_client, 'snmp/etc.snmp.conf.j2', snmp)
    # Write server config file
    render(config_file_daemon, 'snmp/etc.snmpd.conf.j2', snmp)
    # Write access rights config file
    render(config_file_access, 'snmp/usr.snmpd.conf.j2', snmp)
    # Write access rights config file
    render(config_file_user, 'snmp/var.snmpd.conf.j2', snmp)
    # Write daemon configuration file
    render(systemd_override, 'snmp/override.conf.j2', snmp)

    return None

def apply(snmp):
    # Always reload systemd manager configuration
    call('systemctl daemon-reload')

    if 'deleted' in snmp:
        return None

    # start SNMP daemon
    call(f'systemctl restart {systemd_service}')

    # Enable AgentX in FRR
    # This should be done for each daemon individually because common command
    # works only if all the daemons started with SNMP support
    # Following daemons from FRR 9.0/stable have SNMP module compiled in VyOS
    frr_daemons_list = ['zebra', 'bgpd', 'ospf6d', 'ospfd', 'ripd', 'isisd', 'ldpd']
    for frr_daemon in frr_daemons_list:
        call(f'vtysh -c "configure terminal" -d {frr_daemon} -c "agentx" >/dev/null')

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
