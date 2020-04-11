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

import os

from jinja2 import FileSystemLoader, Environment
from psutil import users
from pwd import getpwall, getpwnam
from stat import S_IRUSR, S_IWUSR, S_IRWXU, S_IRGRP, S_IXGRP
from sys import exit

from vyos.config import Config
from vyos.configdict import list_diff
from vyos.defaults import directories as vyos_data_dir
from vyos import ConfigError
from vyos.util import cmd
from vyos.util import call
from vyos.util import DEVNULL


radius_config_file = "/etc/pam_radius_auth.conf"

default_config_data = {
    'deleted': False,
    'add_users': [],
    'del_users': [],
    'radius_server': [],
    'radius_source_address': '',
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
    return cmd(f'/usr/bin/mkpasswd --method=sha-512 {password}')


def get_config():
    login = default_config_data
    conf = Config()
    base_level = ['system', 'login']

    # We do not need to check if the nodes exist or not and bail out early
    # ... this would interrupt the following logic on determine which users
    # should be deleted and which users should stay.
    #
    # All fine so far!

    # Read in all local users and store to list
    for username in conf.list_nodes(base_level + ['user']):
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

    #
    # RADIUS configuration
    #
    conf.set_level(base_level + ['radius'])

    if conf.exists(['source-address']):
        login['radius_source_address'] = conf.return_value(['source-address'])

    # Read in all RADIUS servers and store to list
    for server in conf.list_nodes(['server']):
        server_cfg = {
            'address': server,
            'disabled': False,
            'key': '',
            'port': '1812',
            'timeout': '2'
        }
        conf.set_level(base_level + ['radius', 'server', server])

        # Check if RADIUS server was temporary disabled
        if conf.exists(['disable']):
            server_cfg['disabled'] = True

        # RADIUS shared secret
        if conf.exists(['key']):
            server_cfg['key'] = conf.return_value(['key'])

        # RADIUS authentication port
        if conf.exists(['port']):
            server_cfg['port'] = conf.return_value(['port'])

        # RADIUS session timeout
        if conf.exists(['timeout']):
            server_cfg['timeout'] = conf.return_value(['timeout'])

        # Append individual RADIUS server configuration to global server list
        login['radius_server'].append(server_cfg)

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

    for user in login['add_users']:
        for key in user['public_keys']:
            if not key['type']:
                raise ConfigError('SSH public key type missing for "{}"!'.format(key['name']))

            if not key['key']:
                raise ConfigError('SSH public key for id "{}" missing!'.format(key['name']))

    # At lease one RADIUS server must not be disabled
    if len(login['radius_server']) > 0:
        fail = True
        for server in login['radius_server']:
            if not server['disabled']:
                fail = False
        if fail:
            raise ConfigError('At least one RADIUS server must be active.')


    return None

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

            # env = os.environ.copy()
            # env['vyos_libexec_dir'] = '/usr/libexec/vyos'

            # call("/opt/vyatta/sbin/my_set system login user '{}' authentication plaintext-password ''".format(user['name']),
            #     env=env)
            # call("/opt/vyatta/sbin/my_set system login user '{}' authentication encrypted-password '{}'".format(user['name'], user['password_encrypted']),
            #     env=env)

    if len(login['radius_server']) > 0:
        # Prepare Jinja2 template loader from files
        tmpl_path = os.path.join(vyos_data_dir['data'], 'templates', 'system-login')
        fs_loader = FileSystemLoader(tmpl_path)
        env = Environment(loader=fs_loader)

        tmpl = env.get_template('pam_radius_auth.conf.tmpl')
        config_text = tmpl.render(login)
        with open(radius_config_file, 'w') as f:
            f.write(config_text)

        uid = getpwnam('root').pw_uid
        gid = getpwnam('root').pw_gid
        os.chown(radius_config_file, uid, gid)
        os.chmod(radius_config_file, S_IRUSR | S_IWUSR)
    else:
        if os.path.isfile(radius_config_file):
            os.unlink(radius_config_file)

    return None

def apply(login):
    for user in login['add_users']:
        # make new user using vyatta shell and make home directory (-m),
        # default group of 100 (users)
        command = "useradd -m -N"
        # check if user already exists:
        if user['name'] in get_local_users():
            # update existing account
            command = "usermod"

        # we need to use '' quotes when passing formatted data to the shell
        # else it will not work as some data parts are lost in translation
        command += " -p '{}'".format(user['password_encrypted'])
        command += " -s /bin/vbash"
        if user['full_name']:
            command += " -c '{}'".format(user['full_name'])

        if user['home_dir']:
            command += " -d '{}'".format(user['home_dir'])

        command += " -G frrvty,vyattacfg,sudo,adm,dip,disk"
        command += " {}".format(user['name'])

        try:
            cmd(command)

            uid = getpwnam(user['name']).pw_uid
            gid = getpwnam(user['name']).pw_gid

            # we should not rely on the home dir value stored in user['home_dir']
            # as if a crazy user will choose username root or any other system
            # user this will fail. should be deny using root at all?
            home_dir = getpwnam(user['name']).pw_dir
            # install ssh keys
            ssh_key_dir = home_dir + '/.ssh'
            if not os.path.isdir(ssh_key_dir):
                os.mkdir(ssh_key_dir)
                os.chown(ssh_key_dir, uid, gid)
                os.chmod(ssh_key_dir, S_IRWXU | S_IRGRP | S_IXGRP)

            ssh_key_file = ssh_key_dir + '/authorized_keys';
            with open(ssh_key_file, 'w') as f:
                f.write("# Automatically generated by VyOS\n")
                f.write("# Do not edit, all changes will be lost\n")

                for id in user['public_keys']:
                    line = ''
                    if id['options']:
                        line = '{} '.format(id['options'])

                    line += '{} {} {}\n'.format(id['type'], id['key'], id['name'])
                    f.write(line)

            os.chown(ssh_key_file, uid, gid)
            os.chmod(ssh_key_file, S_IRUSR | S_IWUSR)

        except Exception as e:
            raise ConfigError('Adding user "{}" raised an exception: {}'.format(user['name'], e))

    for user in login['del_users']:
        try:
            # Logout user if he is logged in
            if user in list(set([tmp[0] for tmp in users()])):
                print('{} is logged in, forcing logout'.format(user))
                call('pkill -HUP -u {}'.format(user))

            # Remove user account but leave home directory to be safe
            call(f'userdel -r {user}', stderr=DEVNULL)

        except Exception as e:
            raise ConfigError('Deleting user "{}" raised an exception: {}'.format(user, e))

    #
    # RADIUS configuration
    #
    if len(login['radius_server']) > 0:
        try:
            env = os.environ.copy()
            env['DEBIAN_FRONTEND'] = 'noninteractive'
            # Enable RADIUS in PAM
            cmd("pam-auth-update --package --enable radius", env=env)

            # Make NSS system aware of RADIUS, too
            command = "sed -i -e \'/\smapname/b\' \
                          -e \'/^passwd:/s/\s\s*/&mapuid /\' \
                          -e \'/^passwd:.*#/s/#.*/mapname &/\' \
                          -e \'/^passwd:[^#]*$/s/$/ mapname &/\' \
                          -e \'/^group:.*#/s/#.*/ mapname &/\' \
                          -e \'/^group:[^#]*$/s/: */&mapname /\' \
                          /etc/nsswitch.conf"

            cmd(command)

        except Exception as e:
            raise ConfigError('RADIUS configuration failed: {}'.format(e))

    else:
        try:
            env = os.environ.copy()
            env['DEBIAN_FRONTEND'] = 'noninteractive'

            # Disable RADIUS in PAM
            cmd("pam-auth-update --package --remove radius", env=env)

            command = "sed -i -e \'/^passwd:.*mapuid[ \t]/s/mapuid[ \t]//\' \
                   -e \'/^passwd:.*[ \t]mapname/s/[ \t]mapname//\' \
                   -e \'/^group:.*[ \t]mapname/s/[ \t]mapname//\' \
                   -e \'s/[ \t]*$//\' \
                   /etc/nsswitch.conf"

            cmd(command)

        except Exception as e:
            raise ConfigError('Removing RADIUS configuration failed.\n{}'.format(e))

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
