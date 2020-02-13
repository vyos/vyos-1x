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
from stat import S_IRUSR, S_IWUSR, S_IRWXU, S_IRGRP, S_IXGRP
from subprocess import Popen, PIPE, STDOUT
from psutil import users

from vyos.config import Config
from vyos.configdict import list_diff
from vyos import ConfigError

default_config_data = {
    'deleted': False,
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
    base_level = ['system', 'login', 'user']

    # We do not need to check if the nodes exist or not and bail out early
    # ... this would interrupt the following logic on determine which users
    # should be deleted and which users should stay.
    #
    # All fine so far!

    # Read in all local users and store to list
    for username in conf.list_nodes(base_level):
        user = {
            'name': username,
            'password_plaintext': '',
            'password_encrypted': '!',
            'public_keys': [],
            'full_name': '',
            'home_dir': '/home/' + username,
        }
        conf.set_level(base_level + [username])

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
            conf.set_level(base_level + [username, 'authentication', 'public-keys', id])

            # Public Key portion
            if conf.exists(['key']):
                key['key'] = conf.return_value(['key'])

            # Options for individual public key
            if conf.exists(['options']):
                key['options'] = conf.return_value(['options'])

            # Type of public key
            if conf.exists(['type']):
                key['type'] = conf.return_value(['type'])

            # Append individual public key to list of user keys
            user['public_keys'].append(key)

        login['add_users'].append(user)

    # users no longer existing in the running configuration need to be deleted
    local_users = get_local_users()
    cli_users = [tmp['name'] for tmp in login['add_users']]
    # create a list of all users, cli and users
    all_users = list(set(local_users+cli_users))

    # Remove any normal users that dos not exist in the current configuration.
    # This can happen if user is added but configuration was not saved and
    # system is rebooted.
    login['del_users'] = [tmp for tmp in all_users if tmp not in cli_users]

    return login

def verify(login):
    cur_user = os.environ['SUDO_USER']
    if cur_user in login['del_users']:
        raise ConfigError('Attempting to delete current user: {}'.format(cur_user))

    pass

def generate(login):
    # calculate users encrypted password
    for user in login['add_users']:
        if user['password_plaintext']:
            user['password_encrypted'] = get_crypt_pw(user['password_plaintext'])
            user['password_plaintext'] = ''

            # remove old plaintext password
            # and set new encrypted password
            os.system("vyos_libexec_dir=/usr/libexec/vyos /opt/vyatta/sbin/my_set system login user '{}' authentication plaintext-password '' >/dev/null".format(user['name']))
            os.system("vyos_libexec_dir=/usr/libexec/vyos /opt/vyatta/sbin/my_set system login user '{}' authentication encrypted-password '{}' >/dev/null".format(user['name'], user['password_encrypted']))

    return None

def apply(login):
    for user in login['add_users']:
        # make new user using vyatta shell and make home directory (-m),
        # default group of 100 (users)
        cmd = "useradd -m -N"
        # check if user already exists:
        if user['name'] in get_local_users():
            # update existing account
            cmd = "usermod"

        # we need to use '' quotes when passing formatted data to the shell
        # else it will not work as some data parts are lost in translation
        cmd += " -p '{}'".format(user['password_encrypted'])
        cmd += " -s /bin/vbash"
        if user['full_name']:
            cmd += " -c '{}'".format(user['full_name'])

        if user['home_dir']:
            cmd += " -d '{}'".format(user['home_dir'])

        cmd += " -G frrvty,vyattacfg,sudo,adm,dip,disk"
        cmd += " {}".format(user['name'])

        try:
            os.system(cmd)

            uid = getpwnam(user['name']).pw_uid
            gid = getpwnam(user['name']).pw_gid

            # install ssh keys
            key_dir = '{}/.ssh'.format(user['home_dir'])
            if not os.path.isdir(key_dir):
                os.mkdir(key_dir)
                os.chown(key_dir, uid, gid)
                os.chmod(key_dir, S_IRWXU | S_IRGRP | S_IXGRP)

            key_file = key_dir + '/authorized_keys';
            with open(key_file, 'w') as f:
                f.write("# Automatically generated by VyOS\n")
                f.write("# Do not edit, all changes will be lost\n")

                for id in user['public_keys']:
                    line = ''
                    if id['options']:
                        line = '{} '.format(id['options'])

                    line += '{} {} {}\n'.format(id['type'], id['key'], id['name'])
                    f.write(line)

            os.chown(key_file, uid, gid)
            os.chmod(key_file, S_IRUSR | S_IWUSR)

        except Exception as e:
            raise ConfigError('Adding user "{}" raised an exception: {}'.format(user['name'], e))

    for user in login['del_users']:
        try:
            # Logout user if he is logged in
            if user in list(set([tmp[0] for tmp in users()])):
                print('{} is logged in, forcing logout'.format(user))
                os.system('pkill -HUP -u {}'.format(user))

            # Remove user account but leave home directory to be safe
            os.system('userdel -r {} 2>/dev/null'.format(user))

        except Exception as e:
            raise ConfigError('Deleting user "{}" raised an exception: {}'.format(user, e))

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
