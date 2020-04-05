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
import re

from jinja2 import FileSystemLoader, Environment
from sys import exit

from vyos.config import Config
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError
from vyos.util import run

def get_config():
    c = Config()
    if not c.exists('system syslog'):
        return None
    c.set_level('system syslog')

    config_data = {
        'files': {},
      'console': {},
      'hosts': {},
      'user': {}
    }

    #
    # /etc/rsyslog.d/vyos-rsyslog.conf
    # 'set system syslog global'
    #
    config_data['files'].update(
        {
            'global': {
                'log-file': '/var/log/messages',
                'max-size': 262144,
                'action-on-max-size': '/usr/sbin/logrotate /etc/logrotate.d/vyos-rsyslog',
                'selectors': '*.notice;local7.debug',
                'max-files': '5',
                'preserver_fqdn': False
            }
        }
    )

    if c.exists('global marker'):
        config_data['files']['global']['marker'] = True
        if c.exists('global marker interval'):
            config_data['files']['global'][
                'marker-interval'] = c.return_value('global marker interval')
    if c.exists('global facility'):
        config_data['files']['global'][
            'selectors'] = generate_selectors(c, 'global facility')
    if c.exists('global archive size'):
        config_data['files']['global']['max-size'] = int(
            c.return_value('global archive size')) * 1024
    if c.exists('global archive file'):
        config_data['files']['global'][
            'max-files'] = c.return_value('global archive file')
    if c.exists('global preserve-fqdn'):
        config_data['files']['global']['preserver_fqdn'] = True

    #
    # set system syslog file
    #

    if c.exists('file'):
        filenames = c.list_nodes('file')
        for filename in filenames:
            config_data['files'].update(
                {
                    filename: {
                        'log-file': '/var/log/user/' + filename,
                        'max-files': '5',
                        'action-on-max-size': '/usr/sbin/logrotate /etc/logrotate.d/' + filename,
                        'selectors': '*.err',
                        'max-size': 262144
                    }
                }
            )

            if c.exists('file ' + filename + ' facility'):
                config_data['files'][filename]['selectors'] = generate_selectors(
                    c, 'file ' + filename + ' facility')
            if c.exists('file ' + filename + ' archive size'):
                config_data['files'][filename]['max-size'] = int(
                    c.return_value('file ' + filename + ' archive size')) * 1024
            if c.exists('file ' + filename + ' archive files'):
                config_data['files'][filename]['max-files'] = c.return_value(
                    'file ' + filename + ' archive files')

    # set system syslog console
    if c.exists('console'):
        config_data['console'] = {
            '/dev/console': {
                'selectors': '*.err'
            }
        }

    for f in c.list_nodes('console facility'):
        if c.exists('console facility ' + f + ' level'):
            config_data['console'] = {
                '/dev/console': {
                    'selectors': generate_selectors(c, 'console facility')
                }
            }

    # set system syslog host
    if c.exists('host'):
        rhosts = c.list_nodes('host')
        proto = 'udp'
        for rhost in rhosts:
            for fac in c.list_nodes('host ' + rhost + ' facility'):
                if c.exists('host ' + rhost + ' facility ' + fac + ' protocol'):
                    proto = c.return_value(
                        'host ' + rhost + ' facility ' + fac + ' protocol')
                else:
                    proto = 'udp'

            config_data['hosts'].update(
                {
                    rhost: {
                        'selectors': generate_selectors(c, 'host ' + rhost + ' facility'),
                        'proto': proto
                    }
                }
            )
            if c.exists('host ' + rhost + ' port'):
                config_data['hosts'][rhost][
                    'port'] = c.return_value(['host', rhost, 'port'])

    # set system syslog user
    if c.exists('user'):
        usrs = c.list_nodes('user')
        for usr in usrs:
            config_data['user'].update(
                {
                    usr: {
                        'selectors': generate_selectors(c, 'user ' + usr + ' facility')
                    }
                }
            )

    return config_data


def generate_selectors(c, config_node):
# protocols and security are being mapped here
# for backward compatibility with old configs
# security and protocol mappings can be removed later
    if c.is_tag(config_node):
        nodes = c.list_nodes(config_node)
        selectors = ""
        for node in nodes:
            lvl = c.return_value(config_node + ' ' + node + ' level')
            if lvl == None:
                lvl = "err"
            if lvl == 'all':
                lvl = '*'
            if node == 'all' and node != nodes[-1]:
                selectors += "*." + lvl + ";"
            elif node == 'all':
                selectors += "*." + lvl
            elif node != nodes[-1]:
                if node == 'protocols':
                    node = 'local7'
                if node == 'security':
                    node = 'auth'
                selectors += node + "." + lvl + ";"
            else:
                if node == 'protocols':
                    node = 'local7'
                if node == 'security':
                    node = 'auth'
                selectors += node + "." + lvl
        return selectors


def generate(c):
    if c == None:
        return None

    # Prepare Jinja2 template loader from files
    tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'syslog')
    fs_loader = FileSystemLoader(tmpl_path)
    env = Environment(loader=fs_loader, trim_blocks=True)

    tmpl = env.get_template('rsyslog.conf.tmpl')
    config_text = tmpl.render(c)
    with open('/etc/rsyslog.d/vyos-rsyslog.conf', 'w') as f:
        f.write(config_text)

    # eventually write for each file its own logrotate file, since size is
    # defined it shouldn't matter
    tmpl = env.get_template('logrotate.tmpl')
    config_text = tmpl.render(c)
    with open('/etc/logrotate.d/vyos-rsyslog', 'w') as f:
        f.write(config_text)


def verify(c):
    if c == None:
        return None

    # may be obsolete
    # /etc/rsyslog.conf is generated somewhere and copied over the original (exists in /opt/vyatta/etc/rsyslog.conf)
    # it interferes with the global logging, to make sure we are using a single base, template is enforced here
    #
    if not os.path.islink('/etc/rsyslog.conf'):
        os.remove('/etc/rsyslog.conf')
        os.symlink(
            '/usr/share/vyos/templates/rsyslog/rsyslog.conf', '/etc/rsyslog.conf')

    # /var/log/vyos-rsyslog were the old files, we may want to clean those up, but currently there
    # is a chance that someone still needs it, so I don't automatically remove
    # them
    #

    if c == None:
        return None

    fac = [
        '*', 'auth', 'authpriv', 'cron', 'daemon', 'kern', 'lpr', 'mail', 'mark', 'news', 'protocols', 'security',
          'syslog', 'user', 'uucp', 'local0', 'local1', 'local2', 'local3', 'local4', 'local5', 'local6', 'local7']
    lvl = ['emerg', 'alert', 'crit', 'err',
           'warning', 'notice', 'info', 'debug', '*']

    for conf in c:
        if c[conf]:
            for item in c[conf]:
                for s in c[conf][item]['selectors'].split(";"):
                    f = re.sub("\..*$", "", s)
                    if f not in fac:
                        raise ConfigError(
                            'Invalid facility ' + s + ' set in ' + conf + ' ' + item)
                    l = re.sub("^.+\.", "", s)
                    if l not in lvl:
                        raise ConfigError(
                            'Invalid logging level ' + s + ' set in ' + conf + ' ' + item)


def apply(c):
    if not c:
        return run('systemctl stop syslog')
    return run('systemctl restart syslog')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
