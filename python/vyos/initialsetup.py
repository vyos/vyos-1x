# initialsetup -- functions for setting common values in config file,
# for use in installation and first boot scripts
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

from vyos.utils.auth import make_password_hash
from vyos.utils.auth import split_ssh_public_key

def set_interface_address(config, intf, addr, intf_type="ethernet"):
    config.set(["interfaces", intf_type, intf, "address"], value=addr)
    config.set_tag(["interfaces", intf_type])

def set_host_name(config, hostname):
    config.set(["system", "host-name"], value=hostname)

def set_name_servers(config, servers):
    for s in servers:
        config.set(["system", "name-server"], replace=False, value=s)

def set_default_gateway(config, gateway):
    config.set(["protocols", "static", "route", "0.0.0.0/0", "next-hop", gateway])
    config.set_tag(["protocols", "static", "route"])
    config.set_tag(["protocols", "static", "route", "0.0.0.0/0", "next-hop"])

def set_user_password(config, user, password):
    # Make a password hash
    hash = make_password_hash(password)

    config.set(["system", "login", "user", user, "authentication", "encrypted-password"], value=hash)
    config.set(["system", "login", "user", user, "authentication", "plaintext-password"], value="")

def disable_user_password(config, user):
    config.set(["system", "login", "user", user, "authentication", "encrypted-password"], value="!")
    config.set(["system", "login", "user", user, "authentication", "plaintext-password"], value="")

def set_user_level(config, user, level):
    config.set(["system", "login", "user", user, "level"], value=level)

def set_user_ssh_key(config, user, key_string):
    key = split_ssh_public_key(key_string, defaultname=user)

    config.set(["system", "login", "user", user, "authentication", "public-keys", key["name"], "key"], value=key["data"])
    config.set(["system", "login", "user", user, "authentication", "public-keys", key["name"], "type"], value=key["type"])
    config.set_tag(["system", "login", "user", user, "authentication", "public-keys"])

def create_user(config, user, password=None, key=None, level="admin"):
    config.set(["system", "login", "user", user])
    config.set_tag(["system", "login", "user", user])

    if not key and not password:
        raise ValueError("Must set at least password or SSH public key")

    if password:
        set_user_password(config, user, password)
    else:
        disable_user_password(config, user)

    if key:
        set_user_ssh_key(config, user, key)

    set_user_level(config, user, level)
