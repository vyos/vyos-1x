#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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
#
#

import os
import jinja2

import vyos.config
import vyos.defaults

from vyos import ConfigError

charon_conf_file = "/etc/strongswan.d/charon.conf"


def get_config():
    config = vyos.config.Config()
    data = {
        "accept_unencrypted_mainmode_messages": "no",
        "ikesa_sa_segments": "1",
        "ikesa_sa_table_size": "1",
        "install_routes": "yes",
        "install_virtual_ip": "yes",
        "cisco_unity": "no",
        "strongSwan_id": "no"
    }

    if config.exists("vpn ipsec options unencrypted-mainmode"):
        data["accept_unencrypted_mainmode_messages"] = "yes"

    if config.exists("vpn ipsec options disable-route-autoinstall"):
        data["install_routes"] = "no"

    if config.exists("vpn ipsec options disable-virtual-ip-autoinstall"):
        data["install_virtual_ip"] = "no"

    if config.exists("vpn ipsec options cisco-unity"):
        data["cisco_unity"] = "yes"

    if config.exists("vpn ipsec options strongSwan-id"):
        data["strongSwan_id"] = "yes"

    if config.exists("vpn ipsec options ikesa-sa-table-size"):
        data["ikesa_sa_table_size"] = config.return_value("vpn ipsec options ikesa-sa-table-size")

    if config.exists("vpn ipsec options ikesa-sa-segments"):
        data["ikesa_sa_segments"] = config.return_value("vpn ipsec options ikesa-sa-segments")

    return data

def verify(data):
    pass

def generate(data):
    tmpl_path = os.path.join(vyos.defaults.directories["data"], "templates", "ipsec")
    fs_loader = jinja2.FileSystemLoader(tmpl_path)
    env = jinja2.Environment(loader=fs_loader)


    charon_conf_tmpl = env.get_template("charon.tmpl")
    charon_conf = charon_conf_tmpl.render(data)

    with open(charon_conf_file, 'w') as f:
        f.write(charon_conf)

def apply(data):
    # Do nothing
    # StrongSWAN should only be restarted when actual tunnels are configured
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
