#!/usr/bin/env python3
#
# Copyright (C) 2020-2023 VyOS maintainers and contributors
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

from passlib.hosts import linux_context
from psutil import users
from pwd import getpwall
from pwd import getpwnam
from pwd import getpwuid
from sys import exit
from time import sleep

from vyos.config import Config
from vyos.configverify import verify_vrf
from vyos.defaults import directories
from vyos.template import render
from vyos.template import is_ipv4
from vyos.utils.dict import dict_search
from vyos.utils.file import chown
from vyos.utils.process import cmd
from vyos.utils.process import call
from vyos.utils.process import rc_cmd
from vyos.utils.process import run
from vyos.utils.process import DEVNULL
from vyos import ConfigError
from vyos import airbag
airbag.enable()

autologout_file = "/etc/profile.d/autologout.sh"
limits_file = "/etc/security/limits.d/10-vyos.conf"
radius_config_file = "/etc/pam_radius_auth.conf"
tacacs_pam_config_file = "/etc/tacplus_servers"
tacacs_nss_config_file = "/etc/tacplus_nss.conf"
nss_config_file = "/etc/nsswitch.conf"

# Minimum UID used when adding system users
MIN_USER_UID: int = 1000
# Maximim UID used when adding system users
MAX_USER_UID: int = 59999
# LOGIN_TIMEOUT from /etc/loign.defs minus 10 sec
MAX_RADIUS_TIMEOUT: int = 50
# MAX_RADIUS_TIMEOUT divided by 2 sec (minimum recomended timeout)
MAX_RADIUS_COUNT: int = 8
# Maximum number of supported TACACS servers
MAX_TACACS_COUNT: int = 8

# List of local user accounts that must be preserved
SYSTEM_USER_SKIP_LIST: list = ['radius_user', 'radius_priv_user', 'tacacs0', 'tacacs1',
                              'tacacs2', 'tacacs3', 'tacacs4', 'tacacs5', 'tacacs6',
                              'tacacs7', 'tacacs8', 'tacacs9', 'tacacs10',' tacacs11',
                              'tacacs12', 'tacacs13', 'tacacs14', 'tacacs15']

def get_local_users():
    """Return list of dynamically allocated users (see Debian Policy Manual)"""
    local_users = []
    for s_user in getpwall():
        if getpwnam(s_user.pw_name).pw_uid < MIN_USER_UID:
            continue
        if getpwnam(s_user.pw_name).pw_uid > MAX_USER_UID:
            continue
        if s_user.pw_name in SYSTEM_USER_SKIP_LIST:
            continue
        local_users.append(s_user.pw_name)

    return local_users

def get_shadow_password(username):
    with open('/etc/shadow') as f:
        for user in f.readlines():
            items = user.split(":")
            if username == items[0]:
                return items[1]
    return None

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['system', 'login']
    login = conf.get_config_dict(base, key_mangling=('-', '_'),
                                 no_tag_node_value_mangle=True,
                                 get_first_key=True,
                                 with_recursive_defaults=True)

    # users no longer existing in the running configuration need to be deleted
    local_users = get_local_users()
    cli_users = []
    if 'user' in login:
        cli_users = list(login['user'])

    # prune TACACS global defaults if not set by user
    if login.from_defaults(['tacacs']):
        del login['tacacs']
    # same for RADIUS
    if login.from_defaults(['radius']):
        del login['radius']

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
        # This check is required as the script is also executed from vyos-router
        # init script and there is no SUDO_USER environment variable available
        # during system boot.
        if 'SUDO_USER' in os.environ:
            cur_user = os.environ['SUDO_USER']
            if cur_user in login['rm_users']:
                raise ConfigError(f'Attempting to delete current user: {cur_user}')

    if 'user' in login:
        system_users = getpwall()
        for user, user_config in login['user'].items():
            # Linux system users range up until UID 1000, we can not create a
            # VyOS CLI user which already exists as system user
            for s_user in system_users:
                if s_user.pw_name == user and s_user.pw_uid < MIN_USER_UID:
                    raise ConfigError(f'User "{user}" can not be created, conflict with local system account!')

            for pubkey, pubkey_options in (dict_search('authentication.public_keys', user_config) or {}).items():
                if 'type' not in pubkey_options:
                    raise ConfigError(f'Missing type for public-key "{pubkey}"!')
                if 'key' not in pubkey_options:
                    raise ConfigError(f'Missing key for public-key "{pubkey}"!')

    if {'radius', 'tacacs'} <= set(login):
        raise ConfigError('Using both RADIUS and TACACS at the same time is not supported!')

    # At lease one RADIUS server must not be disabled
    if 'radius' in login:
        if 'server' not in login['radius']:
            raise ConfigError('No RADIUS server defined!')
        sum_timeout: int = 0
        radius_servers_count: int = 0
        fail = True
        for server, server_config in dict_search('radius.server', login).items():
            if 'key' not in server_config:
                raise ConfigError(f'RADIUS server "{server}" requires key!')
            if 'disable' not in server_config:
                sum_timeout += int(server_config['timeout'])
                radius_servers_count += 1
                fail = False

        if fail:
            raise ConfigError('All RADIUS servers are disabled')

        if radius_servers_count > MAX_RADIUS_COUNT:
            raise ConfigError(f'Number of RADIUS servers exceeded maximum of {MAX_RADIUS_COUNT}!')

        if sum_timeout > MAX_RADIUS_TIMEOUT:
            raise ConfigError('Sum of RADIUS servers timeouts '
                              'has to be less or eq 50 sec')

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

    if 'tacacs' in login:
        tacacs_servers_count: int = 0
        fail = True
        for server, server_config in dict_search('tacacs.server', login).items():
            if 'key' not in server_config:
                raise ConfigError(f'TACACS server "{server}" requires key!')
            if 'disable' not in server_config:
                tacacs_servers_count += 1
                fail = False

        if fail:
            raise ConfigError('All RADIUS servers are disabled')

        if tacacs_servers_count > MAX_TACACS_COUNT:
            raise ConfigError(f'Number of TACACS servers exceeded maximum of {MAX_TACACS_COUNT}!')

        verify_vrf(login['tacacs'])

    if 'max_login_session' in login and 'timeout' not in login:
        raise ConfigError('"login timeout" must be configured!')

    return None


def generate(login):
    # calculate users encrypted password
    if 'user' in login:
        for user, user_config in login['user'].items():
            tmp = dict_search('authentication.plaintext_password', user_config)
            if tmp:
                encrypted_password = linux_context.hash(tmp)
                login['user'][user]['authentication']['encrypted_password'] = encrypted_password
                del login['user'][user]['authentication']['plaintext_password']

                # remove old plaintext password and set new encrypted password
                env = os.environ.copy()
                env['vyos_libexec_dir'] = directories['base']

                # Set default commands for re-adding user with encrypted password
                del_user_plain = f"system login user {user} authentication plaintext-password"
                add_user_encrypt = f"system login user {user} authentication encrypted-password '{encrypted_password}'"

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

                ret, out = rc_cmd(f"/opt/vyatta/sbin/my_delete {del_user_plain}", env=env)
                if ret: raise ConfigError(out)
                ret, out = rc_cmd(f"/opt/vyatta/sbin/my_set {add_user_encrypt}", env=env)
                if ret: raise ConfigError(out)
            else:
                try:
                    if get_shadow_password(user) == dict_search('authentication.encrypted_password', user_config):
                        # If the current encrypted bassword matches the encrypted password
                        # from the config - do not update it. This will remove the encrypted
                        # value from the system logs.
                        #
                        # The encrypted password will be set only once during the first boot
                        # after an image upgrade.
                        del login['user'][user]['authentication']['encrypted_password']
                except:
                    pass

    ### RADIUS based user authentication
    if 'radius' in login:
        render(radius_config_file, 'login/pam_radius_auth.conf.j2', login,
                   permission=0o600, user='root', group='root')
    else:
        if os.path.isfile(radius_config_file):
            os.unlink(radius_config_file)

    ### TACACS+ based user authentication
    if 'tacacs' in login:
        render(tacacs_pam_config_file, 'login/tacplus_servers.j2', login,
                   permission=0o644, user='root', group='root')
        render(tacacs_nss_config_file, 'login/tacplus_nss.conf.j2', login,
                   permission=0o644, user='root', group='root')
    else:
        if os.path.isfile(tacacs_pam_config_file):
            os.unlink(tacacs_pam_config_file)
        if os.path.isfile(tacacs_nss_config_file):
            os.unlink(tacacs_nss_config_file)



    # NSS must always be present on the system
    render(nss_config_file, 'login/nsswitch.conf.j2', login,
               permission=0o644, user='root', group='root')

    # /etc/security/limits.d/10-vyos.conf
    if 'max_login_session' in login:
        render(limits_file, 'login/limits.j2', login,
                   permission=0o644, user='root', group='root')
    else:
        if os.path.isfile(limits_file):
            os.unlink(limits_file)

    if 'timeout' in login:
        render(autologout_file, 'login/autologout.j2', login,
                   permission=0o755, user='root', group='root')
    else:
        if os.path.isfile(autologout_file):
            os.unlink(autologout_file)

    return None


def apply(login):
    enable_otp = False
    if 'user' in login:
        for user, user_config in login['user'].items():
            # make new user using vyatta shell and make home directory (-m),
            # default group of 100 (users)
            command = 'useradd --create-home --no-user-group '
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

            command += f' --groups frr,frrvty,vyattacfg,sudo,adm,dip,disk,_kea {user}'
            try:
                cmd(command)
                # we should not rely on the value stored in user_config['home_directory'], as a
                # crazy user will choose username root or any other system user which will fail.
                #
                # XXX: Should we deny using root at all?
                home_dir = getpwnam(user).pw_dir
                # always re-render SSH keys with appropriate permissions
                render(f'{home_dir}/.ssh/authorized_keys', 'login/authorized_keys.j2',
                       user_config, permission=0o600,
                       formater=lambda _: _.replace("&quot;", '"'),
                       user=user, group='users')
            except Exception as e:
                raise ConfigError(f'Adding user "{user}" raised exception: "{e}"')

            # T5875: ensure UID is properly set on home directory if user is re-added
            # the home directory will always exist, as it's created above by --create-home,
            # retrieve current owner of home directory and adjust on demand
            dir_owner = None
            try:
                dir_owner = getpwuid(os.stat(home_dir).st_uid).pw_name
            except:
                pass

            if dir_owner != user:
                    chown(home_dir, user=user, recursive=True)

            # Generate 2FA/MFA One-Time-Pad configuration
            if dict_search('authentication.otp.key', user_config):
                enable_otp = True
                render(f'{home_dir}/.google_authenticator', 'login/pam_otp_ga.conf.j2',
                       user_config, permission=0o400, user=user, group='users')
            else:
                # delete configuration as it's not enabled for the user
                if os.path.exists(f'{home_dir}/.google_authenticator'):
                    os.remove(f'{home_dir}/.google_authenticator')

            # Lock/Unlock local user account
            lock_unlock = '--unlock'
            if 'disable' in user_config:
                lock_unlock = '--lock'
            cmd(f'usermod {lock_unlock} {user}')

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
                while run(f'userdel {user}', stderr=DEVNULL):
                    sleep(0.250)

            except Exception as e:
                raise ConfigError(f'Deleting user "{user}" raised exception: {e}')

    # Enable/disable RADIUS in PAM configuration
    cmd('pam-auth-update --disable radius-mandatory radius-optional')
    if 'radius' in login:
        if login['radius'].get('security_mode', '') == 'mandatory':
            pam_profile = 'radius-mandatory'
        else:
            pam_profile = 'radius-optional'
        cmd(f'pam-auth-update --enable {pam_profile}')

    # Enable/disable TACACS+ in PAM configuration
    cmd('pam-auth-update --disable tacplus-mandatory tacplus-optional')
    if 'tacacs' in login:
        if login['tacacs'].get('security_mode', '') == 'mandatory':
            pam_profile = 'tacplus-mandatory'
        else:
            pam_profile = 'tacplus-optional'
        cmd(f'pam-auth-update --enable {pam_profile}')

    # Enable/disable Google authenticator
    cmd('pam-auth-update --disable mfa-google-authenticator')
    if enable_otp:
        cmd(f'pam-auth-update --enable mfa-google-authenticator')

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
