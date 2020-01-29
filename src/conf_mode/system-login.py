#!/usr/bin/env python3
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

import sys
import os

from pwd import getpwall, getpwnam
from subprocess import Popen, PIPE, STDOUT

from vyos.config import Config
from vyos.configdict import list_diff
from vyos import ConfigError


default_config_data = {
    'deleted': False,
    'radius_server': [],
    'radius_source': '',
    'add_users': [],
    'del_users': []
}

def get_local_users():
    """Returns list of dynamically allocated users (see Debian Policy Manual)"""
    local_users = []
    for p in getpwall():
        username = p[0]
        uid = getpwnam(username).pw_uid
        if uid in range(1000, 29999):
            if username not in ['radius_user', 'radius_priv_user']:
                local_users.append(username)

    return local_users

def get_crypt_pw(password):
    command = '/usr/bin/mkpasswd --method=sha-512 {}'.format(password)
    p = Popen(command, stdout=PIPE, stderr=STDOUT, shell=True)
    tmp = p.communicate()[0].strip()
    return tmp.decode()

def get_config():
    login = default_config_data
    conf = Config()
    base_level = ['system', 'login']

    if not conf.exists(base_level):
        login['deleted'] = True
        return login

    conf.set_level(base_level)

    if conf.exists(['radius', 'source-address']):
        login['radius_source'] = conf.return_value(['radius', 'source-address'])

    # Read in all RADIUS servers and store to list
    for server in conf.list_nodes(['radius', 'server']):
        radius = {
            'address': server,
            'key': '',
            'port': '1812',
            'timeout': '2'
        }
        conf.set_level(base_level + ['radius', 'server', server])

        # RADIUS shared secret
        if conf.exists(['key']):
            radius['key'] = conf.return_value(['key'])

        # RADIUS authentication port
        if conf.exists(['port']):
            radius['port'] = conf.return_value(['port'])

        # RADIUS session timeout
        if conf.exists(['timeout']):
            radius['timeout'] = conf.return_value(['timeout'])

        # Append individual RADIUS server configuration to global server list
        login['radius_server'].append(radius)

    # Read in all local users and store to list
    conf.set_level(base_level)
    for username in conf.list_nodes(['user']):
        user = {
            'name': username,
            'password_plaintext': '',
            'password_encrypted': '!',
            'public_keys': [],
            'full_name': '',
            'home_dir': '/home/' + username,
        }
        conf.set_level(base_level + ['user', username])

        # Plaintext password
        if conf.exists(['authentication', 'plaintext-password']):
            user['password_plaintext'] = conf.return_value(['authentication', 'plaintext-password'])

        # Encrypted password
        if conf.exists(['authentication', 'encrypted-password']):
            user['password_encrypted'] = conf.return_value(['authentication', 'encrypted-password'])

        # User real name
        if conf.exists(['full-name']):
            user['full_name'] = conf.return_value(['full-name'])

        # User home-directory
        if conf.exists(['home-directory']):
            user['home_dir'] = conf.return_value(['home-directory'])

        # Read in public keys
        for id in conf.list_nodes(['authentication', 'public-keys']):
            key = {
                'name': id,
                'key': '',
                'options': '',
                'type': ''
            }
            conf.set_level(base_level + ['user', username, 'authentication', 'public-keys', id])

            # Public Key portion
            if conf.exists(['key']):
                user['key'] = conf.return_value(['key'])

            # Options for individual public key
            if conf.exists(['options']):
                user['options'] = conf.return_value(['options'])

            # Type of public key
            if conf.exists(['type']):
                user['type'] = conf.return_value(['type'])

            # Append individual public key to list of user keys
            user['public_keys'].append(key)

        login['add_users'].append(user)


    return login

def verify(login):

    pass

def generate(login):
    # users no longer existing in the running configuration need to be deleted
    local_users = get_local_users()
    cli_users = [tmp['name'] for tmp in login['add_users']]
    # create a list of all users, cli and users
    all_users = list(set(local_users+cli_users))

    # Remove any normal users that dos not exist in the current configuration.
    # This can happen if user is added but configuration was not saved and
    # system is rebooted.
    login['del_users'] = [tmp for tmp in all_users if tmp not in cli_users]

    # calculate users encrypted password
    for user in login['add_users']:
        if user['password_plaintext']:
            user['password_encrypted'] = get_crypt_pw(user['password_plaintext'])
            user['password_plaintext'] = ''

            # remove old plaintext password
            # and set new encrypted password
            os.system("vyos_libexec_dir=/usr/libexec/vyos /opt/vyatta/sbin/my_set system login user '{}' authentication plaintext-password '' >/dev/null".format(user['name']))
            os.system("vyos_libexec_dir=/usr/libexec/vyos /opt/vyatta/sbin/my_set system login user '{}' authentication encrypted-password '{}' >/dev/null".format(user['name'], user['password_encrypted']))

    pass

def apply(login):
    for user in login['add_users']:
        # make new user using vyatta shell and make home directory (-m),
        # default group of 100 (users)
        cmd = "useradd -m -N"
        # check if user already exists:
        if user['name'] in get_local_users():
            # update existing account
            cmd = "usermod"

        # encrypted password must be quited in '' else it won't work!
        cmd += " -p '{}'".format(user['password_encrypted'])
        cmd += " -s /bin/vbash"
        if user['full_name']:
            cmd += " -c {}".format(user['full_name'])

        if user['home_dir']:
            cmd += " -d '{}'".format(user['home_dir'])

        cmd += " -G frrvty,vyattacfg,sudo,adm,dip,disk"
        cmd += " {}".format(user['name'])

        try:
            os.system(cmd)
        except Exception as e:
            print('Adding user "{}" raised an exception'.format(user))


    for user in login['del_users']:
        try:
            # Remove user account but leave home directory to be safe
            os.system('userdel {}'.format(user))
        except Exception as e:
            print('Deleting user "{}" raised an exception'.format(user))

    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
