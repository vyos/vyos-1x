#!/usr/bin/env python3
#
# Copyright (C) 2018-2023 VyOS maintainers and contributors
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
from sys import exit

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.xml import defaults
from vyos.template import render
from vyos.util import call, is_systemd_service_running
from vyos import ConfigError
from crypt import crypt, mksalt, METHOD_SHA512
from time import sleep

from vyos import airbag
airbag.enable()

cfg_dir        = '/run/ocserv'
ocserv_conf    = cfg_dir + '/ocserv.conf'
ocserv_passwd  = cfg_dir + '/ocpasswd'
radius_cfg     = cfg_dir + '/radiusclient.conf'
radius_servers = cfg_dir + '/radius_servers'

# Generate hash from user cleartext password
def get_hash(password):
    return crypt(password, mksalt(METHOD_SHA512))


def _default_dict_cleanup(origin: dict, default_values: dict) -> dict:
    """
    https://vyos.dev/T2665
    Clear unnecessary key values in merged config by dict_merge function
    :param origin: config
    :type origin: dict
    :param default_values: default values
    :type default_values: dict
    :return: merged dict
    :rtype: dict
    """

    if 'mode' in origin["authentication"] and "radius" in \
            origin["authentication"]["mode"]:
        del origin['authentication']['radius']['server']['port']
        if not origin["authentication"]['radius']['server']:
            raise ConfigError(
                'openconnect authentication mode radius requires at least one RADIUS server')
        default_values_radius_port = \
        default_values['authentication']['radius']['server']['port']
        for server, params in origin['authentication']['radius'][
            'server'].items():
            if 'port' not in params:
                params['port'] = default_values_radius_port
    return origin


def get_config():
    conf = Config()
    base = ['vpn', 'openconnect']
    if not conf.exists(base):
        return None

    ocserv = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrived.
    default_values = defaults(base)
    ocserv = dict_merge(default_values, ocserv)
    ocserv = _default_dict_cleanup(ocserv, default_values)
    return ocserv

def verify(ocserv):
    if ocserv is None:
        return None

    # Check authentication
    if "authentication" in ocserv:
        if "mode" in ocserv["authentication"]:
            if "local" in ocserv["authentication"]["mode"]:
                if 'local_users' not in ocserv["authentication"] or 'username' not in ocserv["authentication"]["local_users"]:
                    raise ConfigError('openconnect authentication mode local requires at least one user')
                else:
                    for user in ocserv["authentication"]["local_users"]["username"]:
                        if not "password" in ocserv["authentication"]["local_users"]["username"][user]:
                            raise ConfigError(f'password required for user {user}')
        else:
            raise ConfigError('openconnect authentication mode required')
    else:
        raise ConfigError('openconnect authentication credentials required')

    # Check ssl
    if "ssl" in ocserv:
        req_cert = ['cert_file', 'key_file']
        for cert in req_cert:
            if not cert in ocserv["ssl"]:
                raise ConfigError('openconnect ssl {0} required'.format(cert.replace('_', '-')))
    else:
        raise ConfigError('openconnect ssl required')

    # Check network settings
    if "network_settings" in ocserv:
        # IPv4 or IPv6 pool must be defined
        ipv4_net_conf = 0
        if "client_ip_settings" in ocserv["network_settings"]:
             if "subnet" in ocserv["network_settings"]["client_ip_settings"]:
                ipv4_net_conf = 1

        ipv6_net_conf = 0
        if 'client_ipv6_pool' in ocserv["network_settings"]:
            if 'prefix' in ocserv["network_settings"]["client_ipv6_pool"]:
                ipv6_net_conf = 1

        if not ipv4_net_conf and not ipv6_net_conf:
            raise ConfigError('openconnect client-ip-settings or client-ipv6-pool required')

        if "push_route" in ocserv["network_settings"]:
            # Replace default route
            if "0.0.0.0/0" in ocserv["network_settings"]["push_route"]:
                ocserv["network_settings"]["push_route"].remove("0.0.0.0/0")
                ocserv["network_settings"]["push_route"].append("default")
        else:
            ocserv["network_settings"]["push_route"] = "default"
    else:
        raise ConfigError('openconnect network settings required')


def generate(ocserv):
    if not ocserv:
        return None

    if "radius" in ocserv["authentication"]["mode"]:
        # Render radius client configuration
        render(radius_cfg, 'ocserv/radius_conf.tmpl', ocserv["authentication"]["radius"])
        # Render radius servers
        render(radius_servers, 'ocserv/radius_servers.tmpl', ocserv["authentication"]["radius"])
    else:
        if "local_users" in ocserv["authentication"]:
            for user in ocserv["authentication"]["local_users"]["username"]:
                ocserv["authentication"]["local_users"]["username"][user]["hash"] = get_hash(ocserv["authentication"]["local_users"]["username"][user]["password"])
            # Render local users
            render(ocserv_passwd, 'ocserv/ocserv_passwd.tmpl', ocserv["authentication"]["local_users"])

    # Render config
    render(ocserv_conf, 'ocserv/ocserv_config.tmpl', ocserv)


def apply(ocserv):
    if not ocserv:
        call('systemctl stop ocserv.service')
        for file in [ocserv_conf, ocserv_passwd]:
            if os.path.exists(file):
                os.unlink(file)
    else:
<<<<<<< HEAD
        call('systemctl restart ocserv.service')
        sleep(1)
        if not is_systemd_service_running("ocserv.service"):
            raise ConfigError('openconnect failed to start, check the logs for details')
=======
        call('systemctl reload-or-restart ocserv.service')
        counter = 0
        while True:
            # exit early when service runs
            if is_systemd_service_running("ocserv.service"):
                break
            sleep(0.250)
            if counter > 5:
                raise ConfigError('openconnect failed to start, check the logs for details')
                break
            counter += 1
>>>>>>> ecb245f13 (T4861: Openconnect replace restart to reload-or-restart)


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
