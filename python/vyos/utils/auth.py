# authutils -- miscelanneous functions for handling passwords and publis keys
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation;
# either version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this library;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import cracklib
import math
import re
import string

from enum import StrEnum
from decimal import Decimal
from pwd import getpwall
from pwd import getpwnam
from vyos.utils.process import cmd

# Minimum UID used when adding system users
MIN_USER_UID: int = 1000
# Maximim UID used when adding system users
MAX_USER_UID: int = 59999
# List of local user accounts that must be preserved
SYSTEM_USER_SKIP_LIST: frozenset = {
    'radius_user',
    'radius_priv_user',
    'tacacs0',
    'tacacs1',
    'tacacs2',
    'tacacs3',
    'tacacs4',
    'tacacs5',
    'tacacs6',
    'tacacs7',
    'tacacs8',
    'tacacs9',
    'tacacs10',
    'tacacs11',
    'tacacs12',
    'tacacs13',
    'tacacs14',
    'tacacs15',
}
DEFAULT_PASSWORD: str = 'vyos'
LOW_ENTROPY_MSG: str = 'should be at least 8 characters long;'
WEAK_PASSWORD_MSG: str = 'The password complexity is too low - @MSG@'
CRACKLIB_ERROR_MSG: str = 'A following error occurred: @MSG@\n' \
    'Possibly the cracklib database is corrupted or is missing. ' \
    'Try reinstalling the python3-cracklib package.'

class EPasswdStrength(StrEnum):
    WEAK = 'Weak'
    DECENT = 'Decent'
    STRONG = 'Strong'
    ERROR = 'Cracklib Error'


def calculate_entropy(charset: str, passwd: str) -> float:
    """
    Calculate the entropy of a password based on the set of characters used
    Uses E = log2(R**L) formula, where
        - R is the range (length) of the character set
        - L is the length of password
    """
    return math.log(math.pow(len(charset), len(passwd)), 2)

def evaluate_strength(passwd: str) -> dict[str, str]:
    """ Evaluates password strength and returns a check result dict """
    charset = (cracklib.ASCII_UPPERCASE + cracklib.ASCII_LOWERCASE +
        string.punctuation + string.digits)

    result = {
        'strength': '',
        'error': '',
    }

    try:
        cracklib.FascistCheck(passwd)
    except ValueError as e:
        # The password is vulnerable to dictionary attack no matter the entropy
        if 'is' in str(e):
            msg = str(e).replace('is', 'should not be')
        else:
            msg = f'should not be {e}'
        result.update(strength=EPasswdStrength.WEAK)
        result.update(error=WEAK_PASSWORD_MSG.replace('@MSG@', msg))
    except Exception as e:
        result.update(strength=EPasswdStrength.ERROR)
        result.update(error=CRACKLIB_ERROR_MSG.replace('@MSG@', str(e)))
    else:
        # Now check the password's entropy
        # Cast to Decimal for more precise rounding
        entropy = Decimal.from_float(calculate_entropy(charset, passwd))

        match round(entropy):
            case e if e in range(0, 59):
                result.update(strength=EPasswdStrength.WEAK)
                result.update(
                    error=WEAK_PASSWORD_MSG.replace('@MSG@', LOW_ENTROPY_MSG)
                )
            case e if e in range(60, 119):
                result.update(strength=EPasswdStrength.DECENT)
            case e if e >= 120:
                result.update(strength=EPasswdStrength.STRONG)

    return result

def make_password_hash(password):
    """ Makes a password hash for /etc/shadow using mkpasswd """

    mkpassword = 'mkpasswd --method=yescrypt --stdin'
    return cmd(mkpassword, input=password, timeout=5)

def split_ssh_public_key(key_string, defaultname=""):
    """ Splits an SSH public key into its components """

    key_string = key_string.strip()
    parts = re.split(r'\s+', key_string)

    if len(parts) == 3:
        key_type, key_data, key_name = parts[0], parts[1], parts[2]
    else:
        key_type, key_data, key_name = parts[0], parts[1], defaultname

    if key_type not in ['ssh-rsa', 'ssh-dss', 'ecdsa-sha2-nistp256', 'ecdsa-sha2-nistp384', 'ecdsa-sha2-nistp521', 'ssh-ed25519']:
        raise ValueError("Bad key type \'{0}\', must be one of must be one of ssh-rsa, ssh-dss, ecdsa-sha2-nistp<256|384|521> or ssh-ed25519".format(key_type))

    return({"type": key_type, "data": key_data, "name": key_name})

def get_current_user() -> str:
    import os
    current_user = 'nobody'
    # During CLI "owner" script execution we use SUDO_USER
    if 'SUDO_USER' in os.environ:
        current_user = os.environ['SUDO_USER']
    # During op-mode or config-mode interactive CLI we use USER
    elif 'USER' in os.environ:
        current_user = os.environ['USER']
    return current_user


def get_local_users(min_uid=MIN_USER_UID, max_uid=MAX_USER_UID) -> list:
    """Return list of dynamically allocated users (see Debian Policy Manual)"""
    local_users = []

    for s_user in getpwall():
        if s_user.pw_uid < min_uid:
            continue
        if s_user.pw_uid > max_uid:
            continue
        if s_user.pw_name in SYSTEM_USER_SKIP_LIST:
            continue
        local_users.append(s_user.pw_name)

    return local_users


def get_user_home_dir(user: str) -> str:
    """Return user's home directory"""
    return getpwnam(user).pw_dir
