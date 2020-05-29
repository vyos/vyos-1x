#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from binascii import hexlify
from time import sleep
from stat import S_IRWXU, S_IXGRP, S_IXOTH, S_IROTH, S_IRGRP
from sys import exit

from vyos.config import Config
from vyos.validate import is_ipv4, is_addr_assigned
from vyos.version import get_version_data
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

config_file_client  = r'/etc/snmp/snmp.conf'
config_file_daemon  = r'/etc/snmp/snmpd.conf'
config_file_access  = r'/usr/share/snmp/snmpd.conf'
config_file_user    = r'/var/lib/snmp/snmpd.conf'
default_script_dir  = r'/config/user-data/'

# SNMP OIDs used to mark auth/priv type
OIDs = {
    'md5' : '.1.3.6.1.6.3.10.1.1.2',
    'sha' : '.1.3.6.1.6.3.10.1.1.3',
    'aes' : '.1.3.6.1.6.3.10.1.2.4',
    'des' : '.1.3.6.1.6.3.10.1.2.2',
    'none': '.1.3.6.1.6.3.10.1.2.1'
}

default_config_data = {
    'listen_on': [],
    'listen_address': [],
    'ipv6_enabled': 'True',
    'communities': [],
    'smux_peers': [],
    'location' : '',
    'description' : '',
    'contact' : '',
    'trap_source': '',
    'trap_targets': [],
    'vyos_user': '',
    'vyos_user_pass': '',
    'version': '999',
    'v3_enabled': 'False',
    'v3_engineid': '',
    'v3_groups': [],
    'v3_traps': [],
    'v3_users': [],
    'v3_views': [],
    'script_ext': []
}

def rmfile(file):
    if os.path.isfile(file):
        os.unlink(file)

def get_config():
    snmp = default_config_data
    conf = Config()
    if not conf.exists('service snmp'):
        return None
    else:
        if conf.exists('system ipv6 disable'):
            snmp['ipv6_enabled'] = False

        conf.set_level('service snmp')

    version_data = get_version_data()
    snmp['version'] = version_data['version']

    # create an internal snmpv3 user of the form 'vyosxxxxxxxxxxxxxxxx'
    # os.urandom(8) returns 8 bytes of random data
    snmp['vyos_user'] = 'vyos' + hexlify(os.urandom(8)).decode('utf-8')
    snmp['vyos_user_pass'] = hexlify(os.urandom(16)).decode('utf-8')

    if conf.exists('community'):
        for name in conf.list_nodes('community'):
            community = {
                'name': name,
                'authorization': 'ro',
                'network_v4': [],
                'network_v6': [],
                'has_source' : False
            }

            if conf.exists('community {0} authorization'.format(name)):
                community['authorization'] = conf.return_value('community {0} authorization'.format(name))

            # Subnet of SNMP client(s) allowed to contact system
            if conf.exists('community {0} network'.format(name)):
                for addr in conf.return_values('community {0} network'.format(name)):
                    if is_ipv4(addr):
                        community['network_v4'].append(addr)
                    else:
                        community['network_v6'].append(addr)

            # IP address of SNMP client allowed to contact system
            if conf.exists('community {0} client'.format(name)):
                for addr in conf.return_values('community {0} client'.format(name)):
                    if is_ipv4(addr):
                        community['network_v4'].append(addr)
                    else:
                        community['network_v6'].append(addr)

            if (len(community['network_v4']) > 0) or (len(community['network_v6']) > 0):
                 community['has_source'] = True

            snmp['communities'].append(community)

    if conf.exists('contact'):
        snmp['contact'] = conf.return_value('contact')

    if conf.exists('description'):
        snmp['description'] = conf.return_value('description')

    if conf.exists('listen-address'):
        for addr in conf.list_nodes('listen-address'):
            port = '161'
            if conf.exists('listen-address {0} port'.format(addr)):
                port = conf.return_value('listen-address {0} port'.format(addr))

            snmp['listen_address'].append((addr, port))

        # Always listen on localhost if an explicit address has been configured
        # This is a safety measure to not end up with invalid listen addresses
        # that are not configured on this system. See https://phabricator.vyos.net/T850
        if not '127.0.0.1' in conf.list_nodes('listen-address'):
            snmp['listen_address'].append(('127.0.0.1', '161'))

        if not '::1' in conf.list_nodes('listen-address'):
            snmp['listen_address'].append(('::1', '161'))

    if conf.exists('location'):
        snmp['location'] = conf.return_value('location')

    if conf.exists('smux-peer'):
        snmp['smux_peers'] = conf.return_values('smux-peer')

    if conf.exists('trap-source'):
        snmp['trap_source'] = conf.return_value('trap-source')

    if conf.exists('trap-target'):
        for target in conf.list_nodes('trap-target'):
            trap_tgt = {
                'target': target,
                'community': '',
                'port': ''
            }

            if conf.exists('trap-target {0} community'.format(target)):
               trap_tgt['community'] = conf.return_value('trap-target {0} community'.format(target))

            if conf.exists('trap-target {0} port'.format(target)):
                trap_tgt['port'] = conf.return_value('trap-target {0} port'.format(target))

            snmp['trap_targets'].append(trap_tgt)

    #
    # 'set service snmp script-extensions'
    #
    if conf.exists('script-extensions'):
        for extname in conf.list_nodes('script-extensions extension-name'):
            conf_script = conf.return_value('script-extensions extension-name {} script'.format(extname))
            # if script has not absolute path, use pre configured path
            if "/" not in conf_script:
                conf_script = default_script_dir + conf_script

            extension = {
                'name': extname,
                'script' : conf_script
            }

            snmp['script_ext'].append(extension)

    #########################################################################
    #                ____  _   _ __  __ ____          _____                 #
    #               / ___|| \ | |  \/  |  _ \  __   _|___ /                 #
    #               \___ \|  \| | |\/| | |_) | \ \ / / |_ \                 #
    #                ___) | |\  | |  | |  __/   \ V / ___) |                #
    #               |____/|_| \_|_|  |_|_|       \_/ |____/                 #
    #                                                                       #
    #     now take care about the fancy SNMP v3 stuff, or bail out eraly    #
    #########################################################################
    if not conf.exists('v3'):
        return snmp
    else:
        snmp['v3_enabled'] = True

    # 'set service snmp v3 engineid'
    if conf.exists('v3 engineid'):
        snmp['v3_engineid'] = conf.return_value('v3 engineid')

    # 'set service snmp v3 group'
    if conf.exists('v3 group'):
        for group in conf.list_nodes('v3 group'):
            v3_group = {
                'name': group,
                'mode': 'ro',
                'seclevel': 'auth',
                'view': ''
            }

            if conf.exists('v3 group {0} mode'.format(group)):
                v3_group['mode'] = conf.return_value('v3 group {0} mode'.format(group))

            if conf.exists('v3 group {0} seclevel'.format(group)):
                v3_group['seclevel'] = conf.return_value('v3 group {0} seclevel'.format(group))

            if conf.exists('v3 group {0} view'.format(group)):
                v3_group['view'] = conf.return_value('v3 group {0} view'.format(group))

            snmp['v3_groups'].append(v3_group)

    # 'set service snmp v3 trap-target'
    if conf.exists('v3 trap-target'):
        for trap in conf.list_nodes('v3 trap-target'):
            trap_cfg = {
                'ipAddr': trap,
                'secName': '',
                'authProtocol': 'md5',
                'authPassword': '',
                'authMasterKey': '',
                'privProtocol': 'des',
                'privPassword': '',
                'privMasterKey': '',
                'ipProto': 'udp',
                'ipPort': '162',
                'type': '',
                'secLevel': 'noAuthNoPriv'
            }

            if conf.exists('v3 trap-target {0} user'.format(trap)):
                # Set the securityName used for authenticated SNMPv3 messages.
                trap_cfg['secName'] = conf.return_value('v3 trap-target {0} user'.format(trap))

            if conf.exists('v3 trap-target {0} auth type'.format(trap)):
                # Set the authentication protocol (MD5 or SHA) used for authenticated SNMPv3 messages
                # cmdline option '-a'
                trap_cfg['authProtocol'] = conf.return_value('v3 trap-target {0} auth type'.format(trap))

            if conf.exists('v3 trap-target {0} auth plaintext-key'.format(trap)):
                # Set the authentication pass phrase used for authenticated SNMPv3 messages.
                # cmdline option '-A'
                trap_cfg['authPassword'] = conf.return_value('v3 trap-target {0} auth plaintext-key'.format(trap))

            if conf.exists('v3 trap-target {0} auth encrypted-key'.format(trap)):
                # Sets the keys to be used for SNMPv3 transactions. These options allow you to set the master authentication keys.
                # cmdline option '-3m'
                trap_cfg['authMasterKey'] = conf.return_value('v3 trap-target {0} auth encrypted-key'.format(trap))

            if conf.exists('v3 trap-target {0} privacy type'.format(trap)):
                # Set the privacy protocol (DES or AES) used for encrypted SNMPv3 messages.
                # cmdline option '-x'
                trap_cfg['privProtocol'] = conf.return_value('v3 trap-target {0} privacy type'.format(trap))

            if conf.exists('v3 trap-target {0} privacy plaintext-key'.format(trap)):
                # Set the privacy pass phrase used for encrypted SNMPv3 messages.
                # cmdline option '-X'
                trap_cfg['privPassword'] = conf.return_value('v3 trap-target {0} privacy plaintext-key'.format(trap))

            if conf.exists('v3 trap-target {0} privacy encrypted-key'.format(trap)):
                # Sets the keys to be used for SNMPv3 transactions. These options allow you to set the master encryption keys.
                # cmdline option '-3M'
                trap_cfg['privMasterKey'] = conf.return_value('v3 trap-target {0} privacy encrypted-key'.format(trap))

            if conf.exists('v3 trap-target {0} protocol'.format(trap)):
                trap_cfg['ipProto'] = conf.return_value('v3 trap-target {0} protocol'.format(trap))

            if conf.exists('v3 trap-target {0} port'.format(trap)):
                trap_cfg['ipPort'] = conf.return_value('v3 trap-target {0} port'.format(trap))

            if conf.exists('v3 trap-target {0} type'.format(trap)):
                trap_cfg['type'] = conf.return_value('v3 trap-target {0} type'.format(trap))

            # Determine securityLevel used for SNMPv3 messages (noAuthNoPriv|authNoPriv|authPriv).
            # Appropriate pass phrase(s) must provided when using any level higher than noAuthNoPriv.
            if trap_cfg['authPassword'] or trap_cfg['authMasterKey']:
                if trap_cfg['privProtocol'] or trap_cfg['privPassword']:
                    trap_cfg['secLevel'] = 'authPriv'
                else:
                    trap_cfg['secLevel'] = 'authNoPriv'

            snmp['v3_traps'].append(trap_cfg)

    # 'set service snmp v3 user'
    if conf.exists('v3 user'):
        for user in conf.list_nodes('v3 user'):
            user_cfg = {
                'name': user,
                'authMasterKey': '',
                'authPassword': '',
                'authProtocol': 'md5',
                'authOID': 'none',
                'group': '',
                'mode': 'ro',
                'privMasterKey': '',
                'privPassword': '',
                'privOID': '',
                'privProtocol': 'des'
            }

            # v3 user {0} auth
            if conf.exists('v3 user {0} auth encrypted-key'.format(user)):
                user_cfg['authMasterKey'] = conf.return_value('v3 user {0} auth encrypted-key'.format(user))

            if conf.exists('v3 user {0} auth plaintext-key'.format(user)):
                user_cfg['authPassword'] = conf.return_value('v3 user {0} auth plaintext-key'.format(user))

            # load default value
            type = user_cfg['authProtocol']
            if conf.exists('v3 user {0} auth type'.format(user)):
                type = conf.return_value('v3 user {0} auth type'.format(user))

            # (re-)update with either default value or value from CLI
            user_cfg['authProtocol'] = type
            user_cfg['authOID'] = OIDs[type]

            # v3 user {0} group
            if conf.exists('v3 user {0} group'.format(user)):
                user_cfg['group'] = conf.return_value('v3 user {0} group'.format(user))

            # v3 user {0} mode
            if conf.exists('v3 user {0} mode'.format(user)):
                user_cfg['mode'] = conf.return_value('v3 user {0} mode'.format(user))

            # v3 user {0} privacy
            if conf.exists('v3 user {0} privacy encrypted-key'.format(user)):
                user_cfg['privMasterKey'] = conf.return_value('v3 user {0} privacy encrypted-key'.format(user))

            if conf.exists('v3 user {0} privacy plaintext-key'.format(user)):
                user_cfg['privPassword'] = conf.return_value('v3 user {0} privacy plaintext-key'.format(user))

            # load default value
            type = user_cfg['privProtocol']
            if conf.exists('v3 user {0} privacy type'.format(user)):
                type = conf.return_value('v3 user {0} privacy type'.format(user))

            # (re-)update with either default value or value from CLI
            user_cfg['privProtocol'] = type
            user_cfg['privOID'] = OIDs[type]

            snmp['v3_users'].append(user_cfg)

    # 'set service snmp v3 view'
    if conf.exists('v3 view'):
        for view in conf.list_nodes('v3 view'):
            view_cfg = {
                'name': view,
                'oids': []
            }

            if conf.exists('v3 view {0} oid'.format(view)):
                for oid in conf.list_nodes('v3 view {0} oid'.format(view)):
                    oid_cfg = {
                        'oid': oid
                    }
                    view_cfg['oids'].append(oid_cfg)
            snmp['v3_views'].append(view_cfg)

    return snmp

def verify(snmp):
    if snmp is None:
        # we can not delete SNMP when LLDP is configured with SNMP
        conf = Config()
        if conf.exists('service lldp snmp enable'):
            raise ConfigError('Can not delete SNMP service, as LLDP still uses SNMP!')

        return None

    ### check if the configured script actually exist
    if snmp['script_ext']:
        for ext in snmp['script_ext']:
            if not os.path.isfile(ext['script']):
                print ("WARNING: script: {} doesn't exist".format(ext['script']))
            else:
                os.chmod(ext['script'], S_IRWXU | S_IXGRP | S_IXOTH | S_IROTH | S_IRGRP)

    for listen in snmp['listen_address']:
        addr = listen[0]
        port = listen[1]

        if is_ipv4(addr):
            # example: udp:127.0.0.1:161
            listen = 'udp:' + addr + ':' + port
        elif snmp['ipv6_enabled']:
            # example: udp6:[::1]:161
            listen = 'udp6:' + '[' + addr + ']' + ':' + port

        # We only wan't to configure addresses that exist on the system.
        # Hint the user if they don't exist
        if is_addr_assigned(addr):
            snmp['listen_on'].append(listen)
        else:
            print('WARNING: SNMP listen address {0} not configured!'.format(addr))

    # bail out early if SNMP v3 is not configured
    if not snmp['v3_enabled']:
        return None

    if 'v3_groups' in snmp.keys():
        for group in snmp['v3_groups']:
            #
            # A view must exist prior to mapping it into a group
            #
            if 'view' in group.keys():
                error = True
                if 'v3_views' in snmp.keys():
                    for view in snmp['v3_views']:
                        if view['name'] == group['view']:
                            error = False
                if error:
                    raise ConfigError('You must create view "{0}" first'.format(group['view']))
            else:
                raise ConfigError('"view" must be specified')

            if not 'mode' in group.keys():
                raise ConfigError('"mode" must be specified')

            if not 'seclevel' in group.keys():
                raise ConfigError('"seclevel" must be specified')

    if 'v3_traps' in snmp.keys():
        for trap in snmp['v3_traps']:
            if trap['authPassword'] and trap['authMasterKey']:
                raise ConfigError('Must specify only one of encrypted-key/plaintext-key for trap auth')

            if trap['authPassword'] == '' and trap['authMasterKey'] == '':
                raise ConfigError('Must specify encrypted-key or plaintext-key for trap auth')

            if trap['privPassword'] and trap['privMasterKey']:
                raise ConfigError('Must specify only one of encrypted-key/plaintext-key for trap privacy')

            if trap['privPassword'] == '' and trap['privMasterKey'] == '':
                raise ConfigError('Must specify encrypted-key or plaintext-key for trap privacy')

            if not 'type' in trap.keys():
                raise ConfigError('v3 trap: "type" must be specified')

            if not 'authPassword' and 'authMasterKey' in trap.keys():
                raise ConfigError('v3 trap: "auth" must be specified')

            if not 'authProtocol' in trap.keys():
                raise ConfigError('v3 trap: "protocol" must be specified')

            if not 'privPassword' and 'privMasterKey' in trap.keys():
                raise ConfigError('v3 trap: "user" must be specified')

    if 'v3_users' in snmp.keys():
        for user in snmp['v3_users']:
            #
            # Group must exist prior to mapping it into a group
            # seclevel will be extracted from group
            #
            if user['group']:
                error = True
                if 'v3_groups' in snmp.keys():
                    for group in snmp['v3_groups']:
                        if group['name'] == user['group']:
                            seclevel = group['seclevel']
                            error = False

                if error:
                    raise ConfigError('You must create group "{0}" first'.format(user['group']))

            # Depending on the configured security level
            # the user has to provide additional info
            if user['authPassword'] and user['authMasterKey']:
                raise ConfigError('Can not mix "encrypted-key" and "plaintext-key" for user auth')

            if (not user['authPassword'] and not user['authMasterKey']):
                raise ConfigError('Must specify encrypted-key or plaintext-key for user auth')

            if user['privPassword'] and user['privMasterKey']:
                raise ConfigError('Can not mix "encrypted-key" and "plaintext-key" for user privacy')

            if user['privPassword'] == '' and user['privMasterKey'] == '':
                raise ConfigError('Must specify encrypted-key or plaintext-key for user privacy')

            if user['mode'] == '':
                raise ConfigError('Must specify user mode ro/rw')

    if 'v3_views' in snmp.keys():
        for view in snmp['v3_views']:
            if not view['oids']:
                raise ConfigError('Must configure an oid')

    return None

def generate(snmp):
    #
    # As we are manipulating the snmpd user database we have to stop it first!
    # This is even save if service is going to be removed
    call('systemctl stop snmpd.service')
    config_files = [config_file_client, config_file_daemon, config_file_access,
                    config_file_user]
    for file in config_files:
        rmfile(file)

    if snmp is None:
        return None

    # Write client config file
    render(config_file_client, 'snmp/etc.snmp.conf.tmpl', snmp)
    # Write server config file
    render(config_file_daemon, 'snmp/etc.snmpd.conf.tmpl', snmp)
    # Write access rights config file
    render(config_file_access, 'snmp/usr.snmpd.conf.tmpl', snmp)
    # Write access rights config file
    render(config_file_user, 'snmp/var.snmpd.conf.tmpl', snmp)

    return None

def apply(snmp):
    if snmp is None:
        return None

    # start SNMP daemon
    call("systemctl restart snmpd.service")

    while (call('systemctl -q is-active snmpd.service') != 0):
        print("service not yet started")
        sleep(0.5)

    # net-snmp is now regenerating the configuration file in the background
    # thus we need to re-open and re-read the file as the content changed.
    # After that we can no read the encrypted password from the config and
    # replace the CLI plaintext password with its encrypted version.
    os.environ["vyos_libexec_dir"] = "/usr/libexec/vyos"
    with open(config_file_user, 'r') as f:
        engineID = ''
        for line in f:
            if line.startswith('usmUser'):
                string = line.split(' ')
                cfg = {
                    'user': string[4].replace(r'"', ''),
                    'auth_pw': string[8],
                    'priv_pw': string[10]
                }
                # No need to take care about the VyOS internal user
                if cfg['user'] == snmp['vyos_user']:
                    continue

                # Now update the running configuration
                #
                # Currently when executing call() the environment does not
                # have the vyos_libexec_dir variable set, see Phabricator T685.
                call('/opt/vyatta/sbin/my_set service snmp v3 user "{0}" auth encrypted-key "{1}" > /dev/null'.format(cfg['user'], cfg['auth_pw']))
                call('/opt/vyatta/sbin/my_set service snmp v3 user "{0}" privacy encrypted-key "{1}" > /dev/null'.format(cfg['user'], cfg['priv_pw']))
                call('/opt/vyatta/sbin/my_delete service snmp v3 user "{0}" auth plaintext-key > /dev/null'.format(cfg['user']))
                call('/opt/vyatta/sbin/my_delete service snmp v3 user "{0}" privacy plaintext-key > /dev/null'.format(cfg['user']))

    # Enable AgentX in FRR
    call('vtysh -c "configure terminal" -c "agentx" >/dev/null')

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
