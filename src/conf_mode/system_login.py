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

import re
import os
import json
from urllib.parse import urlparse

from copy import deepcopy
from passlib.hosts import linux_context
from psutil import users
from sys import exit
from time import sleep

from vyos.base import Warning
from vyos.base import DeprecationWarning
from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configverify import verify_vrf
from vyos.defaults import SSH_DSA_DEPRECATION_WARNING
from vyos.template import render
from vyos.template import is_ipv4
from vyos.utils.auth import DEFAULT_PASSWORD
from vyos.utils.auth import EPasswdStrength
from vyos.utils.auth import evaluate_strength
from vyos.utils.auth import get_current_user
from vyos.utils.auth import get_local_passwd_entries
from vyos.utils.auth import get_local_users
from vyos.utils.auth import get_user_home_dir
from vyos.utils.auth import MIN_USER_UID
from vyos.utils.auth import SYSTEM_USER_SKIP_LIST
from vyos.utils.configfs import delete_cli_node
from vyos.utils.configfs import add_cli_node
from vyos.utils.dict import dict_search
from vyos.utils.file import move_recursive
from vyos.utils.network import is_addr_assigned
from vyos.utils.permission import chown
from vyos.utils.process import cmd
from vyos.utils.process import call
from vyos.utils.process import run
from vyos.utils.process import DEVNULL
from vyos.configdiff import get_config_diff
from vyos import ConfigError
from vyos import airbag
airbag.enable()

autologout_file = "/etc/profile.d/autologout.sh"
limits_file = "/etc/security/limits.d/10-vyos.conf"
radius_config_file = "/etc/pam_radius_auth.conf"
tacacs_pam_config_file = "/etc/tacplus_servers"
tacacs_nss_config_file = "/etc/tacplus_nss.conf"
nss_config_file = "/etc/nsswitch.conf"
login_motd_dsa_warning = r'/run/motd.d/92-vyos-user-dsa-deprecation-warning'

# LOGIN_TIMEOUT from /etc/loign.defs minus 10 sec
MAX_RADIUS_TIMEOUT: int = 50
# MAX_RADIUS_TIMEOUT divided by 2 sec (minimum recommended timeout)
MAX_RADIUS_COUNT: int = 8
# Maximum number of supported TACACS servers
MAX_TACACS_COUNT: int = 8
# Minimum USER id for TACACS users
MIN_TACACS_UID = 900

# As of OpenSSH 9.8p1 in Debian trixie, DSA keys are no longer supported
SSH_DSA_DEPRECATION_WARNING: str = f'{SSH_DSA_DEPRECATION_WARNING} '\
'The following users are using SSH-DSS keys for authentication.'


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

    D = get_config_diff(conf)
    # users no longer existing in the running configuration need to be deleted
    local_users = get_local_users()
    cli_users = []
    if 'user' in login:
        cli_users = list(login['user'])

        for user, user_config in login['user'].items():
            if 'serial' in user_config:
                if 'access' in user_config['serial']:
                    conf_diff = D.get_child_nodes_diff(['system', 'login', 'user', user, 'serial', 'access'], recursive=True)
                    login['user'][user]['serial']['access']['add'] = conf_diff['add']
                    login['user'][user]['serial']['access']['stable'] = conf_diff['stable']

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

    # Build TACACS user mapping
    if 'tacacs' in login:
        login['exclude_users'] = get_local_users(min_uid=0,
                                                 max_uid=MIN_USER_UID) + list(SYSTEM_USER_SKIP_LIST) + cli_users
        login['tacacs_min_uid'] = MIN_TACACS_UID

    set_dependents('ssh', conf)
    return login

def expand_with_origin(lst):
    mapping = {}
    for item in lst:
        nums = list(map(int, re.findall(r'\d+', item)))
        if '-' in item and len(nums) == 2:
            start, end = nums
            numbers = range(start, end + 1)
        else:
            numbers = nums
        for n in numbers:
            if n not in mapping:
                mapping[n] = set()
            mapping[n].add(item)
    return mapping

def verify(login):
    if 'rm_users' in login:
        # This check is required as the script is also executed from vyos-router
        # init script and there is no SUDO_USER environment variable available
        # during system boot.
        tmp = get_current_user()
        if tmp in login['rm_users']:
            raise ConfigError(f'Attempting to delete current user: {tmp}')

    if 'user' in login:
        system_users = get_local_passwd_entries()
        for user, user_config in login['user'].items():
            # Linux system users range up until UID 1000, we can not create a
            # VyOS CLI user which already exists as system user
            for s_user in system_users:
                if s_user.pw_name == user and s_user.pw_uid < MIN_USER_UID:
                    raise ConfigError(f'User "{user}" can not be created, conflict with local system account!')

            plaintext_password = dict_search('authentication.plaintext_password', user_config)
            if plaintext_password == DEFAULT_PASSWORD:
                Warning(f'Default password used for user "{user}" - consider changing it')

            # T6353: Check password for complexity using cracklib.
            # A user password should be sufficiently complex
            failed_check_status = [EPasswdStrength.WEAK, EPasswdStrength.ERROR]
            if plaintext_password and len(plaintext_password) > 0:
                result = evaluate_strength(plaintext_password)
                if result['strength'] in failed_check_status:
                    tmp = result['error']
                    Warning(f'User "{user}" - {tmp}')

            for pubkey, pubkey_options in dict_search('authentication.public_keys', user_config,
                                                      default={}).items():
                if 'type' not in pubkey_options:
                    raise ConfigError(f'Missing type for public-key "{pubkey}"!')
                if 'key' not in pubkey_options:
                    raise ConfigError(f'Missing key for public-key "{pubkey}"!')

            if 'operator' in user_config:
                op_groups = dict_search('operator.group', user_config)
                if op_groups:
                    for og in op_groups:
                        if dict_search(f'operator_group.{og}', login) is None:
                            raise ConfigError(f'Operator group {og} does not exist')
                else:
                    raise ConfigError(f'User {user} is configured as an operator but is not assigned to any operator groups')

    # Deprecation Warning for SSH DSS keys.
    gen_header = True
    if 'user' in login:
        for user, user_config in login['user'].items():
            for pubkey, pubkey_options in (dict_search('authentication.public_keys', user_config) or {}).items():
                if 'type' in pubkey_options and pubkey_options['type'] == 'ssh-dss':
                    if gen_header:
                        gen_header = False
                        DeprecationWarning(SSH_DSA_DEPRECATION_WARNING)
                    print(f'User "{user}" with deprecated public-key named: {pubkey}')
            if 'serial' in user_config:
                if 'access' in user_config['serial']:
                    existing = {}
                    new = {}
                    if 'stable' in user_config['serial']['access']:
                        existing = expand_with_origin(user_config['serial']['access']['stable'])
                    if 'add' in user_config['serial']['access']:
                        new = expand_with_origin(user_config['serial']['access']['add'])

                    common_origins = set()
                    for num, new_sources in new.items():
                        if num in existing:
                            existing_sources = existing[num]
                            if set(new_sources) != set(existing_sources):
                                common_origins.update(new_sources)

                    common_origins_list = sorted(common_origins)

                    if common_origins:
                        raise ConfigError(f"serial-access range {common_origins_list} cannot be set with existing {user_config['serial']['access']['stable']}")

    # No more than 1 authentication methods
    if len({'radius', 'tacacs', 'saml'}.intersection(set(login))) > 1:
        raise ConfigError('Only one of RADIUS, TACACS and SAML can be used at the same time!')

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

        if addresses := dict_search('radius.source_address', login):
            ipv4_count = 0
            ipv6_count = 0
            radius_vrf = dict_search('radius.vrf', login)
            for address in addresses:
                if is_ipv4(address): ipv4_count += 1
                else:                ipv6_count += 1

                if not is_addr_assigned(address, vrf=radius_vrf):
                    Warning(f'Specified RADIUS source-address "{address}" is not assigned!')

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
            raise ConfigError('All TACACS servers are disabled')

        if tacacs_servers_count > MAX_TACACS_COUNT:
            raise ConfigError(f'Number of TACACS servers exceeded maximum of {MAX_TACACS_COUNT}!')

        verify_vrf(login['tacacs'])

        if tmp := dict_search('tacacs.source_address', login):
            tacacs_vrf = dict_search('tacacs.vrf', login)
            if not is_addr_assigned(tmp, vrf=tacacs_vrf):
                Warning(f'Specified TACACS source-address "{tmp}" is not assigned!')

    if 'saml' in login:
        # Verify name
        if not 'name' in login['saml']:
            raise ConfigError("SAML provider name must be set")

        # Verify metadata-url
        if not 'metadata_url' in login['saml']:
            raise ConfigError("SAML metadata-url must be set")
        metadata_url = login['saml']['metadata_url']
        try:
            url_res = urlparse(metadata_url)
            if not url_res.scheme in ("https", "http") or not url_res.netloc:
                raise ConfigError("SAML metadata-url must be a valid http/https url")
        except ValueError:
            raise ConfigError("SAML metadata-url must be a valid http/https url [ValueError]")

        if not 'entityID' in login['saml']:
            login['saml']['entityID'] = r'https://perle.com/sso/saml'
            print(f"Warning: No entityID set using default entityID '{login['saml']['entityID']}'")
        entityID = login['saml']['entityID']
        try:
            url_res = urlparse(entityID)
            if not url_res.scheme in ("https", "http") or not url_res.netloc:
                raise ConfigError("SAML entityID must be a valid http/https uri")
        except ValueError:
            raise ConfigError("SAML entityID must be a valid http/https uri [ValueError]")

        # Verify default sso level
        if not 'default_sso_level' in login['saml']:
            raise ConfigError("Default sso level must be set")

        saml_config = login['saml']
        user_levels = ("admin", "operator")

        if not any(level in saml_config for level in user_levels):
            sso_level = saml_config['default_sso_level']
            print(f"Warning: No user/attribute config set for saml, All users will be set to '{sso_level}'.")

        for level in user_levels:
            level_config = saml_config.get(level, {})
            attr_types = ("req", "suff")

            for attr_type in attr_types:
                attrs = level_config.get(attr_type, {})
                for attr_name, attr_config in attrs.items():
                    values = attr_config.get('value', [])
                    if not values:
                        raise ConfigError(f"SAML attribute '{attr_name}' under '{level}/{attr_type}' must have values")
            EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$")
            for username in level_config.get("user", []):
                if not EMAIL_REGEX.match(username):
                    raise ConfigError("SAML usernames must be emails")

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

                # Set default commands for re-adding user with encrypted password
                del_user_plain = ['system', 'login', 'user', user, 'authentication', 'plaintext-password']
                add_user_encrypt = ['system', 'login', 'user', user, 'authentication', 'encrypted-password']

                delete_cli_node(del_user_plain)
                add_cli_node(add_user_encrypt, value=encrypted_password)

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

    SAML_CONFIG_DIR = r'/etc/saml-sp'
    SAML_CONFIG_FILE = r'saml.conf'
    if 'saml' in login:
        try:
            if not os.path.exists(SAML_CONFIG_DIR):
                os.makedirs(SAML_CONFIG_DIR, exist_ok=True)
            with open(f"{SAML_CONFIG_DIR}/{SAML_CONFIG_FILE}", 'w') as saml_conf_file:
                json.dump(login.get("saml"), saml_conf_file, indent=4)
        except Exception:
            raise ConfigError("SAML: Could not generate config file")
    elif os.path.isfile(f"{SAML_CONFIG_DIR}/{SAML_CONFIG_FILE}"):
        try:
            os.unlink(f"{SAML_CONFIG_DIR}/{SAML_CONFIG_FILE}")
        except Exception as e:
            print(f"Warning: could not remove {SAML_CONFIG_DIR}/{SAML_CONFIG_FILE}, error: {str(e)}")

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

    # Operator groups and group membership
    operator_config = {'users': {}, 'groups': {}}
    if 'user' in login:
        for user, user_config in login['user'].items():
            op_groups = dict_search('operator.group', user_config)
            if op_groups:
                operator_config['users'][user] = op_groups

    if 'operator_group' in login:
        operator_config['groups'] = login['operator_group']

        # Convert permissions strings to list
        # so that the operational command runner doesn't have to
        for g in operator_config['groups']:
            policy = dict_search(f'command_policy.allow', operator_config['groups'][g])
            if policy is not None:
                policy = list(map(lambda s: re.split(r'\s+', s), policy))
                operator_config['groups'][g]['command_policy']['allow'] = policy

    # Generate MOTD informing the user(s) for possible deprecated SSH keys
    tmp = deepcopy(login)
    tmp['ssh_dsa_deprecation_warning'] = f'DEPRECATION WARNING: {SSH_DSA_DEPRECATION_WARNING}'
    render(login_motd_dsa_warning, 'login/motd_user_dsa_warning.j2', tmp,
        permission=0o644, user='root', group='root')

    with open('/etc/vyos/operators.json', 'w') as of:
        json.dump(operator_config, of)

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

            home_directory = dict_search('home_directory', user_config)
            if not home_directory:
                home_directory = f'/home/{user}'
            command += f" --home '{home_directory}'"

            if 'operator' not in user_config:
                command += f' --groups frr,frrvty,vyattacfg,sudo,adm,dip,disk,_kea,vpp'
                command += ',tss' # PERLE - support for TPM - add tss group

            command += f' {user}'

            try:
                cmd(command)
                # we should not rely on the value stored in user_config['home_directory'], as a
                # crazy user will choose username root or any other system user which will fail.
                #
                # XXX: Should we deny using root at all?
                home_dir = get_user_home_dir(user)
                # always re-render SSH keys with appropriate permissions
                render(f'{home_dir}/.ssh/authorized_keys', 'login/authorized_keys.j2',
                       user_config, permission=0o600,
                       formater=lambda _: _.replace("&quot;", '"'),
                       user=user, group='users')

                principals_file = f'{home_dir}/.ssh/authorized_principals'
                if dict_search('authentication.principal', user_config):
                    render(principals_file, 'login/authorized_principals.j2',
                           user_config, permission=0o600,
                           formater=lambda _: _.replace("&quot;", '"'),
                           user=user, group='users')
                else:
                    if os.path.exists(principals_file):
                        os.unlink(principals_file)

            except Exception as e:
                raise ConfigError(f'Adding user "{user}" raised exception: "{e}"')

            # After invoking 'useradd' for each user, if /var/.users_backups/{user} exists, restore the
            # backed up files to the newly created home directory. This reinstates the user's
            # SSH environment and avoids loss of access or trust relationships due to the user
            # creation process, which does not copy such custom files by default.
            #
            # More details: https://github.com/vyos/vyos-1x/pull/4678#pullrequestreview-3169648265
            backup_directory = f"/var/.users_backups/{user}"
            if command.startswith('useradd') and os.path.exists(backup_directory):
                move_recursive(backup_directory, home_dir)
                chown(home_dir, user=user, group='users', recursive=True)

            # T5875: ensure UID is properly set on home directory if user is re-added
            # the home directory will always exist, as it's created above by --create-home,
            # retrieve current owner of home directory and adjust on demand
            dir_owner = None
            try:
                dir_owner = get_local_passwd_entries(os.stat(home_dir).st_uid).pw_name
            except:
                pass

            if dir_owner != user:
                    chown(home_dir, user=user, recursive=True)

            # Generate 2FA/MFA One-Time-Pad configuration
            google_auth_file = f'{home_dir}/.google_authenticator'
            if dict_search('authentication.otp.key', user_config):
                enable_otp = True
                render(google_auth_file, 'login/pam_otp_ga.conf.j2',
                       user_config, permission=0o400, user=user, group='users')
            else:
                # delete configuration as it's not enabled for the user
                if os.path.exists(google_auth_file):
                    os.unlink(google_auth_file)

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

                home_dir = get_user_home_dir(user)
                # Remove SSH authorized keys file
                authorized_keys_file = f'{home_dir}/.ssh/authorized_keys'
                if os.path.exists(authorized_keys_file):
                    os.unlink(authorized_keys_file)

                # Remove SSH authorized principals file
                principals_file = f'{home_dir}/.ssh/authorized_principals'
                if os.path.exists(principals_file):
                    os.unlink(principals_file)

                # Remove Google Authenticator file
                google_auth_file = f'{home_dir}/.google_authenticator'
                if os.path.exists(google_auth_file):
                    os.unlink(google_auth_file)

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

    try:
        cmd('systemctl stop saml-sp')
        cmd('systemctl disable saml-sp')
        cmd('pam-auth-update --disable saml_auth')
        if 'saml' in login:
            cmd('pam-auth-update --enable saml_auth')
            cmd('systemctl start saml-sp')
            cmd('systemctl enable saml-sp')
    except Exception as e:
        print(f"WARNING SAML: could not toggle SAML services: '{str(e)}'")

    # Enable/disable Google authenticator
    cmd('pam-auth-update --disable mfa-google-authenticator')
    if enable_otp:
        cmd('pam-auth-update --enable mfa-google-authenticator')

    call_dependents()
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
