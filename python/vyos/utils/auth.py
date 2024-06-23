# authutils -- miscelanneous functions for handling passwords and publis keys
#
# Copyright (C) 2023-2024 VyOS maintainers and contributors
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

import re

from vyos.utils.process import cmd

def make_password_hash(password):
    """ Makes a password hash for /etc/shadow using mkpasswd """

    mkpassword = 'mkpasswd --method=sha-512 --stdin'
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
