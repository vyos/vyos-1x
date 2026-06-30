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

import json
import os

from sys import exit

from vyos.base import Warning
from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_vrf
from vyos.defaults import systemd_services
from vyos.snmpv3_hashgen import plaintext_to_md5
from vyos.snmpv3_hashgen import plaintext_to_sha1
from vyos.snmpv3_hashgen import random
from vyos.template import render
from vyos.utils.configfs import delete_cli_node
from vyos.utils.configfs import add_cli_node
from vyos.utils.dict import dict_search
from vyos.utils.network import is_addr_assigned
from vyos.utils.process import call
from vyos.utils.permission import chmod_755
from vyos.version import get_version_data
from vyos import ConfigError
from vyos import airbag
airbag.enable()

config_file_client  = r'/etc/snmp/snmp.conf'
config_file_daemon  = r'/etc/snmp/snmpd.conf'
config_file_access  = r'/usr/share/snmp/snmpd.conf'
config_file_user    = r'/var/lib/snmp/snmpd.conf'
default_script_dir  = r'/config/user-data/'
systemd_override    = r'/run/systemd/system/snmpd.service.d/override.conf'
systemd_service     = systemd_services['snmpd']

# WWAN SNMP trap emitter (igos-wwan-snmp-traps): the env file is the unit's
# ConditionPathExists trigger; the 0600 targets file carries the per-target
# snmptrap argv (incl. v3 credentials) on tmpfs.
WWAN_TRAP_ENV_FILE     = r'/etc/default/igos-wwan-snmp-traps'
WWAN_TRAP_TARGETS_FILE = r'/run/igos-wwan-snmp-traps.targets.json'

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
    # options which we need to update into the dictionary retrieved.
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

    if 'script_extensions' in snmp and 'extension_name' in snmp['script_extensions']:
        for key, val in snmp['script_extensions']['extension_name'].items():
            if 'script' not in val:
                continue
            script_path = val['script']
            # if script has not absolute path, use pre configured path
            if not os.path.isabs(script_path):
                script_path = os.path.join(default_script_dir, script_path)

            snmp['script_extensions']['extension_name'][key]['script'] = script_path

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
        Warning('Custom OIDs are enabled and may lead to system instability and high resource consumption')


    verify_vrf(snmp)

    # bail out early if SNMP v3 is not configured
    if 'v3' not in snmp:
        return None

    if 'user' in snmp['v3']:
        if 'engineid' not in snmp['v3']:
            raise ConfigError('EngineID must be configured for SNMPv3!')

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
        # SNMPv3 uses a hashed password. If CLI defines a plaintext password,
        # we will hash it in the background and replace the CLI node!
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

                    cli_base = ['service', 'snmp', 'v3', 'user', user, 'auth']
                    delete_cli_node(cli_base + ['plaintext-password'])
                    add_cli_node(cli_base + ['encrypted-password'], value=tmp)

                if dict_search('privacy.plaintext_password', user_config) is not None:
                    tmp = hash(dict_search('privacy.plaintext_password', user_config),
                        dict_search('v3.engineid', snmp))

                    snmp['v3']['user'][user]['privacy']['encrypted_password'] = tmp
                    del snmp['v3']['user'][user]['privacy']['plaintext_password']

                    cli_base = ['service', 'snmp', 'v3', 'user', user, 'privacy']
                    delete_cli_node(cli_base + ['plaintext-password'])
                    add_cli_node(cli_base + ['encrypted-password'], value=tmp)

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
        # Stop the WWAN SNMP trap emitter — no destination configured.
        call('systemctl stop igos-wwan-snmp-traps.service')
        for path in (WWAN_TRAP_ENV_FILE, WWAN_TRAP_TARGETS_FILE):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        return None

    # start SNMP daemon
    call(f'systemctl reload-or-restart {systemd_service}')

    # Propagate trap-target changes to the WWAN trap emitter.  Best-effort:
    # the emitter only runs if the WWAN subsystem is configured, so we
    # simply re-render the EnvironmentFile if it already exists, then
    # restart the unit.  If no WWAN is configured the unit is a no-op
    # (gated by ConditionPathExists=).
    _sync_wwan_snmp_trap_env(snmp)
    return None


def _sync_wwan_snmp_trap_env(snmp):
    """Render the WWAN trap emitter's destination set from SNMP trap-targets.

    Produces a JSON targets file consumed by ``igos-wwan-snmp-traps`` — one
    entry per configured trap-target, each a complete ``snmptrap(1)`` argv
    prefix (version + auth flags + ``proto:host:port``).  Both the v1/v2c
    community trap-targets (``service snmp trap-target``) and the SNMPv3
    trap-targets (``service snmp v3 trap-target``, authNoPriv/authPriv,
    trap/inform) are emitted, to any number of sinks — mirroring exactly how
    the snmpd.conf template renders ``trap2sink`` / ``trapsess``.

    When no trap-targets are configured the emitter is stopped and its files
    removed.  WWAN-presence gating is handled by the unit itself
    (``BindsTo=igos-wwan-manager.service``), so this is safe to render even
    when WWAN is not configured: the bound unit simply stays stopped.
    """
    targets = _wwan_trap_argv_targets(snmp)
    if not targets:
        # No trap destinations — stop emitter and clean up both files.
        call('systemctl stop igos-wwan-snmp-traps.service')
        for path in (WWAN_TRAP_ENV_FILE, WWAN_TRAP_TARGETS_FILE):
            try:
                os.unlink(path)
            except FileNotFoundError:
                pass
        return

    # Targets file carries v3 credentials → write 0600 and keep it on tmpfs.
    payload = json.dumps({'targets': [{'argv': argv} for argv in targets]})
    _write_private(WWAN_TRAP_TARGETS_FILE, payload)

    # Env file: the unit's ConditionPathExists trigger + pointers for the
    # emitter.  No secrets live here (they are in the 0600 targets file).
    env_body = (
        '# Auto-generated by service_snmp.py — do not edit by hand.\n'
        'IGOS_SNMPTRAP_BIN=/usr/bin/snmptrap\n'
        f'IGOS_SNMPTRAP_TARGETS_FILE={WWAN_TRAP_TARGETS_FILE}\n'
    )
    _write_private(WWAN_TRAP_ENV_FILE, env_body)
    call('systemctl reload-or-restart igos-wwan-snmp-traps.service')


def _wwan_trap_argv_targets(snmp):
    """Build a list of snmptrap(1) argv prefixes from the SNMP config.

    Each prefix ends with the ``proto:host:port`` destination; the WWAN trap
    emitter appends the uptime, notification OID and varbinds.  v1/v2c targets
    come from ``snmp['trap_target']`` (community → ``-v 2c``); v3 targets from
    ``snmp['v3']['trap_target']`` with the same flag mapping the snmpd.conf
    ``trapsess`` directive uses.
    """
    targets = []

    # ── v1/v2c community trap-targets (snmpd renders these as trap2sink,
    #    i.e. SNMPv2c) ─────────────────────────────────────────────────────
    for addr, cfg in (snmp.get('trap_target') or {}).items():
        cfg = cfg or {}
        proto = 'udp6' if _is_ipv6(addr) else 'udp'
        community = cfg.get('community', 'public')
        port = cfg.get('port', '162')
        dest = f'{proto}:{_bracketize(addr)}:{port}'
        targets.append(['-v', '2c', '-c', community, dest])

    # ── SNMPv3 trap-targets ─────────────────────────────────────────────
    v3 = snmp.get('v3') or {}
    engineid = v3.get('engineid')
    for addr, cfg in (v3.get('trap_target') or {}).items():
        cfg = cfg or {}
        base = cfg.get('protocol', 'udp')
        proto = f'{base}6' if _is_ipv6(addr) else base
        port = cfg.get('port', '162')
        argv = ['-v', '3']
        if cfg.get('type') == 'inform':
            argv += ['-Ci']
        if engineid:
            argv += ['-e', engineid]
        user = cfg.get('user')
        if user:
            argv += ['-u', user]
        auth = cfg.get('auth') or {}
        if auth.get('plaintext_password') or auth.get('encrypted_password'):
            argv += ['-a', (auth.get('type') or 'md5').upper()]
            if auth.get('plaintext_password'):
                argv += ['-A', auth['plaintext_password']]
            else:
                argv += ['-3m', auth['encrypted_password']]
            privacy = cfg.get('privacy') or {}
            if privacy.get('plaintext_password') or privacy.get('encrypted_password'):
                argv += ['-x', (privacy.get('type') or 'des').upper()]
                if privacy.get('plaintext_password'):
                    argv += ['-X', privacy['plaintext_password']]
                else:
                    argv += ['-3M', privacy['encrypted_password']]
                argv += ['-l', 'authPriv']
            else:
                argv += ['-l', 'authNoPriv']
        else:
            argv += ['-l', 'noAuthNoPriv']
        argv += [f'{proto}:{_bracketize(addr)}:{port}']
        targets.append(argv)

    return targets


def _is_ipv6(addr):
    """True for an IPv6 literal (trap-target addresses are pre-validated)."""
    return ':' in str(addr)


def _bracketize(addr):
    """Wrap an IPv6 literal in brackets for snmptrap's host:port syntax."""
    return f'[{addr}]' if _is_ipv6(addr) else str(addr)


def _write_private(path, content):
    """Atomically write *content* to *path* with 0600 permissions."""
    tmp = f'{path}.tmp'
    fd = os.open(tmp, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, 'w') as f:
        f.write(content)
    os.replace(tmp, path)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
