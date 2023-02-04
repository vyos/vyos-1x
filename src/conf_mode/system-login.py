#!/usr/bin/env python3
#
# Copyright (C) 2020-2022 VyOS maintainers and contributors
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

from crypt import crypt
from crypt import METHOD_SHA512
from psutil import users
from pwd import getpwall
from pwd import getpwnam
from spwd import getspnam
from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.configverify import verify_vrf
from vyos.template import render
from vyos.template import is_ipv4
from vyos.util import cmd
from vyos.util import call
from vyos.util import run
from vyos.util import DEVNULL
from vyos.util import dict_search
from vyos.xml import defaults
from vyos import ConfigError
from vyos import airbag
airbag.enable()

autologout_file = "/etc/profile.d/autologout.sh"
radius_config_file = "/etc/pam_radius_auth.conf"

def get_local_users():
    """Return list of dynamically allocated users (see Debian Policy Manual)"""
    local_users = []
    for s_user in getpwall():
        uid = getpwnam(s_user.pw_name).pw_uid
        if uid in range(1000, 29999):
            if s_user.pw_name not in ['radius_user', 'radius_priv_user']:
                local_users.append(s_user.pw_name)

    return local_users


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'login']
    login = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 no_tag_node_value_mangle=True, get_first_key=True)

    # users no longer existing in the running configuration need to be deleted
    local_users = get_local_users()
    cli_users = []
    if 'user' in login:
        cli_users = list(login['user'])

        # XXX: T2665: we can not safely rely on the defaults() when there are
        # tagNodes in place, it is better to blend in the defaults manually.
        default_values = defaults(base + ['user'])
        for user in login['user']:
            login['user'][user] = dict_merge(default_values, login['user'][user])

    # XXX: T2665: we can not safely rely on the defaults() when there are
    # tagNodes in place, it is better to blend in the defaults manually.
    default_values = defaults(base + ['radius', 'server'])
    for server in dict_search('radius.server', login) or []:
        login['radius']['server'][server] = dict_merge(default_values,
            login['radius']['server'][server])

    # create a list of all users, cli and users
    all_users = list(set(local_users + cli_users))
    # We will remove any normal users that dos not exist in the current
    # configuration. This can happen if user is added but configuration was not
    # saved and system is rebooted.
    rm_users = [tmp for tmp in all_users if tmp not in cli_users]
    if rm_users: login.update({'rm_users' : rm_users})

    return login

def verify(login):
    if 'rm_users' in login:
        cur_user = os.environ['SUDO_USER']
        if cur_user in login['rm_users']:
            raise ConfigError(f'Attempting to delete current user: {cur_user}')

    if 'user' in login:
        system_users = getpwall()
        for user, user_config in login['user'].items():
            # Linux system users range up until UID 1000, we can not create a
            # VyOS CLI user which already exists as system user
            for s_user in system_users:
                if s_user.pw_name == user and s_user.pw_uid < 1000:
                    raise ConfigError(f'User "{user}" can not be created, conflict with local system account!')

            for pubkey, pubkey_options in (dict_search('authentication.public_keys', user_config) or {}).items():
                if 'type' not in pubkey_options:
                    raise ConfigError(f'Missing type for public-key "{pubkey}"!')
                if 'key' not in pubkey_options:
                    raise ConfigError(f'Missing key for public-key "{pubkey}"!')

    # At lease one RADIUS server must not be disabled
    if 'radius' in login:
        if 'server' not in login['radius']:
            raise ConfigError('No RADIUS server defined!')

        fail = True
        for server, server_config in dict_search('radius.server', login).items():
            if 'key' not in server_config:
                raise ConfigError(f'RADIUS server "{server}" requires key!')

            if 'disabled' not in server_config:
                fail = False
                continue
        if fail:
            raise ConfigError('All RADIUS servers are disabled')

        verify_vrf(login['radius'])

        if 'source_address' in login['radius']:
            ipv4_count = 0
            ipv6_count = 0
            for address in login['radius']['source_address']:
                if is_ipv4(address): ipv4_count += 1
                else:                ipv6_count += 1

            if ipv4_count > 1:
                raise ConfigError('Only one IPv4 source-address can be set!')
            if ipv6_count > 1:
                raise ConfigError('Only one IPv6 source-address can be set!')

    return None


def generate(login):
    # calculate users encrypted password
    if 'user' in login:
        for user, user_config in login['user'].items():
            tmp = dict_search('authentication.plaintext_password', user_config)
            if tmp:
                encrypted_password = crypt(tmp, METHOD_SHA512)
                login['user'][user]['authentication']['encrypted_password'] = encrypted_password
                del login['user'][user]['authentication']['plaintext_password']

                # remove old plaintext password and set new encrypted password
                env = os.environ.copy()
                env['vyos_libexec_dir'] = '/usr/libexec/vyos'

                # Set default commands for re-adding user with encrypted password
                del_user_plain = f"system login user '{user}' authentication plaintext-password"
                add_user_encrypt = f"system login user '{user}' authentication encrypted-password '{encrypted_password}'"

                lvl = env['VYATTA_EDIT_LEVEL']
                # We're in config edit level, for example "edit system login"
                # Change default commands for re-adding user with encrypted password
                if lvl != '/':
                    # Replace '/system/login' to 'system login'
                    lvl = lvl.strip('/').split('/')
                    # Convert command str to list
                    del_user_plain = del_user_plain.split()
                    # New command exclude level, for example "edit system login"
                    del_user_plain = del_user_plain[len(lvl):]
                    # Convert string to list
                    del_user_plain = " ".join(del_user_plain)

                    add_user_encrypt = add_user_encrypt.split()
                    add_user_encrypt = add_user_encrypt[len(lvl):]
                    add_user_encrypt = " ".join(add_user_encrypt)

                call(f"/opt/vyatta/sbin/my_delete {del_user_plain}", env=env)
                call(f"/opt/vyatta/sbin/my_set {add_user_encrypt}", env=env)
            else:
                try:
                    if getspnam(user).sp_pwdp == dict_search('authentication.encrypted_password', user_config):
                        # If the current encrypted bassword matches the encrypted password
                        # from the config - do not update it. This will remove the encrypted
                        # value from the system logs.
                        #
                        # The encrypted password will be set only once during the first boot
                        # after an image upgrade.
                        del login['user'][user]['authentication']['encrypted_password']
                except:
                    pass

    if 'radius' in login:
        render(radius_config_file, 'login/pam_radius_auth.conf.j2', login,
                   permission=0o600, user='root', group='root')
    else:
        if os.path.isfile(radius_config_file):
            os.unlink(radius_config_file)

    if 'timeout' in login:
        render(autologout_file, 'login/autologout.j2', login,
                   permission=0o755, user='root', group='root')
    else:
        if os.path.isfile(autologout_file):
            os.unlink(autologout_file)

    return None


def apply(login):
    if 'user' in login:
        for user, user_config in login['user'].items():
            # make new user using vyatta shell and make home directory (-m),
            # default group of 100 (users)
            command = 'useradd --create-home --no-user-group'
            # check if user already exists:
            if user in get_local_users():
                # update existing account
                command = 'usermod'

            # all accounts use /bin/vbash
            command += ' --shell /bin/vbash'
            # we need to use '' quotes when passing formatted data to the shell
            # else it will not work as some data parts are lost in translation
            tmp = dict_search('authentication.encrypted_password', user_config)
            if tmp: command += f" --password '{tmp}'"

            tmp = dict_search('full_name', user_config)
            if tmp: command += f" --comment '{tmp}'"

            tmp = dict_search('home_directory', user_config)
            if tmp: command += f" --home '{tmp}'"
            else: command += f" --home '/home/{user}'"

            command += f' --groups frr,frrvty,vyattacfg,sudo,adm,dip,disk {user}'
            try:
                cmd(command)

                # we should not rely on the value stored in
                # user_config['home_directory'], as a crazy user will choose
                # username root or any other system user which will fail.
                #
                # XXX: Should we deny using root at all?
                home_dir = getpwnam(user).pw_dir
                render(f'{home_dir}/.ssh/authorized_keys', 'login/authorized_keys.j2',
                       user_config, permission=0o600,
                       formater=lambda _: _.replace("&quot;", '"'),
                       user=user, group='users')

            except Exception as e:
                raise ConfigError(f'Adding user "{user}" raised exception: "{e}"')

            # Generate 2FA/MFA One-Time-Pad configuration
            if dict_search('authentication.otp.key', user_config):
                render(f'{home_dir}/.google_authenticator', 'login/pam_otp_ga.conf.j2',
                       user_config, permission=0o400, user=user, group='users')
            else:
                # delete configuration as it's not enabled for the user
                if os.path.exists(f'{home_dir}/.google_authenticator'):
                    os.remove(f'{home_dir}/.google_authenticator')

    if 'rm_users' in login:
        for user in login['rm_users']:
            try:
                # Disable user to prevent re-login
                call(f'usermod -s /sbin/nologin {user}')

                # Logout user if he is still logged in
                if user in list(set([tmp[0] for tmp in users()])):
                    print(f'{user} is logged in, forcing logout!')
                    # re-run command until user is logged out
                    while run(f'pkill -HUP -u {user}'):
                        sleep(0.250)

                # Remove user account but leave home directory in place. Re-run
                # command until user is removed - userdel might return 8 as
                # SSH sessions are not all yet properly cleaned away, thus we
                # simply re-run the command until the account wen't away
                while run(f'userdel --remove {user}', stderr=DEVNULL):
                    sleep(0.250)

            except Exception as e:
                raise ConfigError(f'Deleting user "{user}" raised exception: {e}')

    #
    # RADIUS configuration
    #
    env = os.environ.copy()
    env['DEBIAN_FRONTEND'] = 'noninteractive'
    try:
        if 'radius' in login:
            # Enable RADIUS in PAM
            cmd('pam-auth-update --package --enable radius', env=env)
            # Make NSS system aware of RADIUS
            # This fancy snipped was copied from old Vyatta code
            command = "sed -i -e \'/\smapname/b\' \
                          -e \'/^passwd:/s/\s\s*/&mapuid /\' \
                          -e \'/^passwd:.*#/s/#.*/mapname &/\' \
                          -e \'/^passwd:[^#]*$/s/$/ mapname &/\' \
                          -e \'/^group:.*#/s/#.*/ mapname &/\' \
                          -e \'/^group:[^#]*$/s/: */&mapname /\' \
                          /etc/nsswitch.conf"
        else:
            # Disable RADIUS in PAM
            cmd('pam-auth-update --package --remove radius', env=env)
            # Drop RADIUS from NSS NSS system
            # This fancy snipped was copied from old Vyatta code
            command = "sed -i -e \'/^passwd:.*mapuid[ \t]/s/mapuid[ \t]//\' \
                   -e \'/^passwd:.*[ \t]mapname/s/[ \t]mapname//\' \
                   -e \'/^group:.*[ \t]mapname/s/[ \t]mapname//\' \
                   -e \'s/[ \t]*$//\' \
                   /etc/nsswitch.conf"

        cmd(command)
    except Exception as e:
        raise ConfigError(f'RADIUS configuration failed: {e}')

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
