#!/usr/bin/env python3
#
# Copyright (C) 2021 VyOS maintainers and contributors
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
from re import compile as re_compile
from re import M as re_M
from sys import exit

from vyos import ConfigError
from vyos import airbag
from vyos.config import Config
from vyos.logger import syslog
from vyos.util import read_file, write_file, run
airbag.enable()

# path to daemons config and config status files
config_file = '/etc/frr/daemons'
vyos_status_file = '/tmp/vyos-config-status'
# path to watchfrr for FRR control
watchfrr = '/usr/lib/frr/watchfrr.sh'


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'frr']
    if not conf.exists(base):
        return {}

    frr_config = conf.get_config_dict(base)

    return frr_config


def daemons_config_parse(daemons_config):
    # create regex for parsing daemons options
    regex_daemon_config = re_compile(
        r'^(?P<daemon_name>\w+)_options="(?P<daemon_options>.*)"$', re_M)
    # create empty dict for config
    daemons_config_dict = {}
    # fill dictionary with actual config
    for daemon in regex_daemon_config.finditer(daemons_config):
        daemon_name = daemon.group('daemon_name')
        daemon_options = daemon.group('daemon_options')
        daemons_config_dict[daemon_name] = daemon_options

    # return daemons config
    return (daemons_config_dict)


def verify(frr_config):
    # Nothing to verify here
    pass


def generate(frr_config):
    # read daemons config file
    daemons_config = read_file(config_file)
    daemons_config_current = daemons_config
    daemons_config_dict = daemons_config_parse(daemons_config)

    # configure SNMP integration
    frr_snmp = frr_config.get('frr', {}).get('snmp', {})
    # prepare regex for matching modules
    regex_snmp = re_compile(r'^.* -M snmp.*$')
    regex_bmp = re_compile(r'^.* -M bmp.*$')
    regex_irdp = re_compile(r'^.* -M irdp.*$')
    # check each daemon's config
    for (daemon_name, daemon_options) in daemons_config_dict.items():
        # check if SNMP integration is enabled in the config file
        snmp_enabled = regex_snmp.match(daemon_options)
        # check if BMP is enabled in the config file
        bmp_enabled = regex_bmp.match(daemon_options)
        # check if IRDP is enabled in the config file
        irdp_enabled = regex_irdp.match(daemon_options)

        # enable SNMP integration
        if daemon_name in frr_snmp and not snmp_enabled:
            daemon_options_new = f'{daemon_options} -M snmp'
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')
            daemon_options = daemon_options_new
        # disable SNMP integration
        if daemon_name not in frr_snmp and snmp_enabled:
            daemon_options_new = daemon_options.replace(' -M snmp', '')
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')
            daemon_options = daemon_options_new

        # enable BMP
        if daemon_name == 'bgpd' and 'bmp' in frr_config.get(
                'frr', {}) and not bmp_enabled:
            daemon_options_new = f'{daemon_options} -M bmp'
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')
            daemon_options = daemon_options_new
        # disable BMP
        if daemon_name == 'bgpd' and 'bmp' not in frr_config.get(
                'frr', {}) and bmp_enabled:
            daemon_options_new = daemon_options.replace(' -M bmp', '')
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')
            daemon_options = daemon_options_new

        # enable IRDP
        if daemon_name == 'zebra' and 'irdp' in frr_config.get(
                'frr', {}) and not irdp_enabled:
            daemon_options_new = f'{daemon_options} -M irdp'
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')
            daemon_options = daemon_options_new
        # disable IRDP
        if daemon_name == 'zebra' and 'irdp' not in frr_config.get(
                'frr', {}) and irdp_enabled:
            daemon_options_new = daemon_options.replace(' -M irdp', '')
            daemons_config = daemons_config.replace(
                f'{daemon_name}_options=\"{daemon_options}\"',
                f'{daemon_name}_options=\"{daemon_options_new}\"')

    # update configuration file if this is necessary
    if daemons_config != daemons_config_current:
        write_file(config_file, daemons_config)
        frr_config['config_file_changed'] = True


def apply(frr_config):
    # check if this is initial commit during boot or intiated by CLI
    # if the file exists, this must be CLI commit
    commit_type_cli = Path(vyos_status_file).exists()
    # display warning to user
    if commit_type_cli and frr_config.get('config_file_changed'):
        # Since FRR restart is not safe thing, better to give
        # control over this to users
        print('''
        You need to reboot a router (preferred) or restart FRR
        to apply changes in modules settings
        ''')
    # restart FRR automatically. DUring the initial boot this should be
    # safe in most cases
    if not commit_type_cli and frr_config.get('config_file_changed'):
        syslog.warning('Restarting FRR to apply changes in modules')
        run(f'{watchfrr} restart')


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
