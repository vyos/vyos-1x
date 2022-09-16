#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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
from vyos.pki import wrap_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.util import call
from vyos.util import check_port_availability
from vyos.util import is_systemd_service_running
from vyos.util import is_listen_port_bind_service
from vyos.util import dict_search
from vyos.xml import defaults
from vyos import ConfigError
from crypt import crypt, mksalt, METHOD_SHA512
from time import sleep

from vyos import airbag
airbag.enable()

cfg_dir        = '/run/ocserv'
ocserv_conf    = cfg_dir + '/ocserv.conf'
ocserv_passwd  = cfg_dir + '/ocpasswd'
ocserv_otp_usr = cfg_dir + '/users.oath'
radius_cfg     = cfg_dir + '/radiusclient.conf'
radius_servers = cfg_dir + '/radius_servers'

# Generate hash from user cleartext password
def get_hash(password):
    return crypt(password, mksalt(METHOD_SHA512))

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

    if "local" in ocserv["authentication"]["mode"]:
        # workaround a "know limitation" - https://phabricator.vyos.net/T2665
        del ocserv['authentication']['local_users']['username']['otp']
        if not ocserv["authentication"]["local_users"]["username"]:
            raise ConfigError('openconnect mode local required at least one user')
        default_ocserv_usr_values = default_values['authentication']['local_users']['username']['otp']
        for user, params in ocserv['authentication']['local_users']['username'].items():
            # Not every configuration requires OTP settings
            if ocserv['authentication']['local_users']['username'][user].get('otp'):
                ocserv['authentication']['local_users']['username'][user]['otp'] = dict_merge(default_ocserv_usr_values, ocserv['authentication']['local_users']['username'][user]['otp'])

    if ocserv:
        ocserv['pki'] = conf.get_config_dict(['pki'], key_mangling=('-', '_'),
                                get_first_key=True, no_tag_node_value_mangle=True)

    return ocserv

def verify(ocserv):
    if ocserv is None:
        return None
    # Check if listen-ports not binded other services
    # It can be only listen by 'ocserv-main'
    for proto, port in ocserv.get('listen_ports').items():
        if check_port_availability(ocserv['listen_address'], int(port), proto) is not True and \
                not is_listen_port_bind_service(int(port), 'ocserv-main'):
            raise ConfigError(f'"{proto}" port "{port}" is used by another service')

    # Check authentication
    if "authentication" in ocserv:
        if "mode" in ocserv["authentication"]:
            if "local" in ocserv["authentication"]["mode"]:
                if "radius" in ocserv["authentication"]["mode"]:
                    raise ConfigError('OpenConnect authentication modes are mutually-exclusive, remove either local or radius from your configuration')
                if not ocserv["authentication"]["local_users"]:
                    raise ConfigError('openconnect mode local required at least one user')
                if not ocserv["authentication"]["local_users"]["username"]:
                    raise ConfigError('openconnect mode local required at least one user')
                else:
                    # For OTP mode: verify that each local user has an OTP key
                    if "otp" in ocserv["authentication"]["mode"]["local"]:
                        users_wo_key = []
                        for user, user_config in ocserv["authentication"]["local_users"]["username"].items():
                            # User has no OTP key defined
                            if dict_search('otp.key', user_config) == None:
                                users_wo_key.append(user)
                        if users_wo_key:
                            raise ConfigError(f'OTP enabled, but no OTP key is configured for these users:\n{users_wo_key}')
                    # For password (and default) mode: verify that each local user has password
                    if "password" in ocserv["authentication"]["mode"]["local"] or "otp" not in ocserv["authentication"]["mode"]["local"]:
                        users_wo_pswd = []
                        for user in ocserv["authentication"]["local_users"]["username"]:
                            if not "password" in ocserv["authentication"]["local_users"]["username"][user]:
                                users_wo_pswd.append(user)
                        if users_wo_pswd:
                            raise ConfigError(f'password required for users:\n{users_wo_pswd}')
        else:
            raise ConfigError('openconnect authentication mode required')
    else:
        raise ConfigError('openconnect authentication credentials required')

    # Check ssl
    if 'ssl' not in ocserv:
        raise ConfigError('openconnect ssl required')

    if not ocserv['pki'] or 'certificate' not in ocserv['pki']:
        raise ConfigError('PKI not configured')

    ssl = ocserv['ssl']
    if 'certificate' not in ssl:
        raise ConfigError('openconnect ssl certificate required')

    cert_name = ssl['certificate']

    if cert_name not in ocserv['pki']['certificate']:
        raise ConfigError('Invalid openconnect ssl certificate')

    cert = ocserv['pki']['certificate'][cert_name]

    if 'certificate' not in cert:
        raise ConfigError('Missing certificate in PKI')

    if 'private' not in cert or 'key' not in cert['private']:
        raise ConfigError('Missing private key in PKI')

    if 'ca_certificate' in ssl:
        if 'ca' not in ocserv['pki']:
            raise ConfigError('PKI not configured')

        if ssl['ca_certificate'] not in ocserv['pki']['ca']:
            raise ConfigError('Invalid openconnect ssl CA certificate')

    # Check network settings
    if "network_settings" in ocserv:
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
        render(radius_cfg, 'ocserv/radius_conf.j2', ocserv["authentication"]["radius"])
        # Render radius servers
        render(radius_servers, 'ocserv/radius_servers.j2', ocserv["authentication"]["radius"])
    elif "local" in ocserv["authentication"]["mode"]:
        # if mode "OTP", generate OTP users file parameters
        if "otp" in ocserv["authentication"]["mode"]["local"]:
            if "local_users" in ocserv["authentication"]:
                for user in ocserv["authentication"]["local_users"]["username"]:
                    # OTP token type from CLI parameters:
                    otp_interval = str(ocserv["authentication"]["local_users"]["username"][user]["otp"].get("interval"))
                    token_type = ocserv["authentication"]["local_users"]["username"][user]["otp"].get("token_type")
                    otp_length = str(ocserv["authentication"]["local_users"]["username"][user]["otp"].get("otp_length"))
                    if token_type == "hotp-time":
                        otp_type = "HOTP/T" + otp_interval
                    elif token_type == "hotp-event":
                        otp_type = "HOTP/E"
                    else:
                        otp_type = "HOTP/T" + otp_interval
                    ocserv["authentication"]["local_users"]["username"][user]["otp"]["token_tmpl"] = otp_type + "/" + otp_length
        # if there is a password, generate hash
        if "password" in ocserv["authentication"]["mode"]["local"] or not "otp" in ocserv["authentication"]["mode"]["local"]:
            if "local_users" in ocserv["authentication"]:
                for user in ocserv["authentication"]["local_users"]["username"]:
                    ocserv["authentication"]["local_users"]["username"][user]["hash"] = get_hash(ocserv["authentication"]["local_users"]["username"][user]["password"])

        if "password-otp" in ocserv["authentication"]["mode"]["local"]:
            # Render local users ocpasswd
            render(ocserv_passwd, 'ocserv/ocserv_passwd.j2', ocserv["authentication"]["local_users"])
            # Render local users OTP keys
            render(ocserv_otp_usr, 'ocserv/ocserv_otp_usr.j2', ocserv["authentication"]["local_users"])
        elif "password" in ocserv["authentication"]["mode"]["local"]:
            # Render local users ocpasswd
            render(ocserv_passwd, 'ocserv/ocserv_passwd.j2', ocserv["authentication"]["local_users"])
        elif "otp" in ocserv["authentication"]["mode"]["local"]:
            # Render local users OTP keys
            render(ocserv_otp_usr, 'ocserv/ocserv_otp_usr.j2', ocserv["authentication"]["local_users"])
        else:
            # Render local users ocpasswd
            render(ocserv_passwd, 'ocserv/ocserv_passwd.j2', ocserv["authentication"]["local_users"])
    else:
        if "local_users" in ocserv["authentication"]:
            for user in ocserv["authentication"]["local_users"]["username"]:
                ocserv["authentication"]["local_users"]["username"][user]["hash"] = get_hash(ocserv["authentication"]["local_users"]["username"][user]["password"])
            # Render local users
            render(ocserv_passwd, 'ocserv/ocserv_passwd.j2', ocserv["authentication"]["local_users"])

    if "ssl" in ocserv:
        cert_file_path = os.path.join(cfg_dir, 'cert.pem')
        cert_key_path = os.path.join(cfg_dir, 'cert.key')
        ca_cert_file_path = os.path.join(cfg_dir, 'ca.pem')

        if 'certificate' in ocserv['ssl']:
            cert_name = ocserv['ssl']['certificate']
            pki_cert = ocserv['pki']['certificate'][cert_name]

            with open(cert_file_path, 'w') as f:
                f.write(wrap_certificate(pki_cert['certificate']))

            if 'private' in pki_cert and 'key' in pki_cert['private']:
                with open(cert_key_path, 'w') as f:
                    f.write(wrap_private_key(pki_cert['private']['key']))

        if 'ca_certificate' in ocserv['ssl']:
            ca_name = ocserv['ssl']['ca_certificate']
            pki_ca_cert = ocserv['pki']['ca'][ca_name]

            with open(ca_cert_file_path, 'w') as f:
                f.write(wrap_certificate(pki_ca_cert['certificate']))

    # Render config
    render(ocserv_conf, 'ocserv/ocserv_config.j2', ocserv)


def apply(ocserv):
    if not ocserv:
        call('systemctl stop ocserv.service')
        for file in [ocserv_conf, ocserv_passwd, ocserv_otp_usr]:
            if os.path.exists(file):
                os.unlink(file)
    else:
        call('systemctl restart ocserv.service')
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


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
