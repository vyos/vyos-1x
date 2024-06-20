#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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

from vyos.base import Warning
from vyos.config import Config
from vyos.configverify import verify_pki_certificate
from vyos.configverify import verify_pki_ca_certificate
from vyos.pki import find_chain
from vyos.pki import encode_certificate
from vyos.pki import load_certificate
from vyos.pki import wrap_private_key
from vyos.template import render
from vyos.utils.dict import dict_search
from vyos.utils.file import write_file
from vyos.utils.network import check_port_availability
from vyos.utils.network import is_listen_port_bind_service
from vyos.utils.process import call
from vyos.utils.process import is_systemd_service_running
from vyos import ConfigError
from passlib.hash import sha512_crypt
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
    return sha512_crypt.hash(password)

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['vpn', 'openconnect']
    if not conf.exists(base):
        return None

    ocserv = conf.get_config_dict(base, key_mangling=('-', '_'),
                                  get_first_key=True,
                                  with_recursive_defaults=True,
                                  with_pki=True)

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

    # Check accounting
    if "accounting" in ocserv:
        if "mode" in ocserv["accounting"] and "radius" in ocserv["accounting"]["mode"]:
            if not origin["accounting"]['radius']['server']:
                raise ConfigError('OpenConnect accounting mode radius requires at least one RADIUS server')
            if "authentication" not in ocserv or "mode" not in ocserv["authentication"]:
                raise ConfigError('Accounting depends on OpenConnect authentication configuration')
            elif "radius" not in ocserv["authentication"]["mode"]:
                raise ConfigError('RADIUS accounting must be used with RADIUS authentication')

    # Check authentication
    if "authentication" in ocserv:
        if "mode" in ocserv["authentication"]:
            if ("local" in ocserv["authentication"]["mode"] and
                "radius" in ocserv["authentication"]["mode"]):
                    raise ConfigError('OpenConnect authentication modes are mutually-exclusive, remove either local or radius from your configuration')
            if "radius" in ocserv["authentication"]["mode"]:
                if not ocserv["authentication"]['radius']['server']:
                    raise ConfigError('OpenConnect authentication mode radius requires at least one RADIUS server')
            if "local" in ocserv["authentication"]["mode"]:
                if not ocserv.get("authentication", {}).get("local_users"):
                    raise ConfigError('OpenConnect mode local required at least one user')
                if not ocserv["authentication"]["local_users"]["username"]:
                    raise ConfigError('OpenConnect mode local required at least one user')
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

            # Validate that if identity-based-config is configured all child config nodes are set
            if 'identity_based_config' in ocserv["authentication"]:
                if 'disabled' not in ocserv["authentication"]["identity_based_config"]:
                    Warning("Identity based configuration files is a 3rd party addition. Use at your own risk, this might break the ocserv daemon!")
                    if 'mode' not in ocserv["authentication"]["identity_based_config"]:
                        raise ConfigError('OpenConnect radius identity-based-config enabled but mode not selected')
                    elif 'group' in ocserv["authentication"]["identity_based_config"]["mode"] and "radius" not in ocserv["authentication"]["mode"]:
                        raise ConfigError('OpenConnect config-per-group must be used with radius authentication')
                    if 'directory' not in ocserv["authentication"]["identity_based_config"]:
                        raise ConfigError('OpenConnect identity-based-config enabled but directory not set')
                    if 'default_config' not in ocserv["authentication"]["identity_based_config"]:
                        raise ConfigError('OpenConnect identity-based-config enabled but default-config not set')
        else:
            raise ConfigError('OpenConnect authentication mode required')
    else:
        raise ConfigError('OpenConnect authentication credentials required')

    # Check ssl
    if 'ssl' not in ocserv:
        raise ConfigError('SSL missing on OpenConnect config!')

    if 'certificate' not in ocserv['ssl']:
        raise ConfigError('SSL certificate missing on OpenConnect config!')
    verify_pki_certificate(ocserv, ocserv['ssl']['certificate'])

    if 'ca_certificate' in ocserv['ssl']:
        for ca_cert in ocserv['ssl']['ca_certificate']:
            verify_pki_ca_certificate(ocserv, ca_cert)

    # Check network settings
    if "network_settings" in ocserv:
        if "push_route" in ocserv["network_settings"]:
            # Replace default route
            if "0.0.0.0/0" in ocserv["network_settings"]["push_route"]:
                ocserv["network_settings"]["push_route"].remove("0.0.0.0/0")
                ocserv["network_settings"]["push_route"].append("default")
        else:
            ocserv["network_settings"]["push_route"] = ["default"]
    else:
        raise ConfigError('OpenConnect network settings required!')

def generate(ocserv):
    if not ocserv:
        return None

    if "radius" in ocserv["authentication"]["mode"]:
        if dict_search(ocserv, 'accounting.mode.radius'):
            # Render radius client configuration
            render(radius_cfg, 'ocserv/radius_conf.j2', ocserv)
            merged_servers = ocserv["accounting"]["radius"]["server"] | ocserv["authentication"]["radius"]["server"]
            # Render radius servers
            # Merge the accounting and authentication servers into a single dictionary
            render(radius_servers, 'ocserv/radius_servers.j2', {'server': merged_servers})
        else:
            # Render radius client configuration
            render(radius_cfg, 'ocserv/radius_conf.j2', ocserv)
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


        if 'certificate' in ocserv['ssl']:
            cert_name = ocserv['ssl']['certificate']
            pki_cert = ocserv['pki']['certificate'][cert_name]

            loaded_pki_cert = load_certificate(pki_cert['certificate'])
            loaded_ca_certs = {load_certificate(c['certificate'])
                for c in ocserv['pki']['ca'].values()} if 'ca' in ocserv['pki'] else {}

            cert_full_chain = find_chain(loaded_pki_cert, loaded_ca_certs)

            write_file(cert_file_path,
                '\n'.join(encode_certificate(c) for c in cert_full_chain))

            if 'private' in pki_cert and 'key' in pki_cert['private']:
                write_file(cert_key_path, wrap_private_key(pki_cert['private']['key']))

        if 'ca_certificate' in ocserv['ssl']:
            ca_cert_file_path = os.path.join(cfg_dir, 'ca.pem')
            ca_chains = []

            for ca_name in ocserv['ssl']['ca_certificate']:
                pki_ca_cert = ocserv['pki']['ca'][ca_name]
                loaded_ca_cert = load_certificate(pki_ca_cert['certificate'])
                ca_full_chain = find_chain(loaded_ca_cert, loaded_ca_certs)
                ca_chains.append(
                    '\n'.join(encode_certificate(c) for c in ca_full_chain))

            write_file(ca_cert_file_path, '\n'.join(ca_chains))

    # Render config
    render(ocserv_conf, 'ocserv/ocserv_config.j2', ocserv)


def apply(ocserv):
    if not ocserv:
        call('systemctl stop ocserv.service')
        for file in [ocserv_conf, ocserv_passwd, ocserv_otp_usr]:
            if os.path.exists(file):
                os.unlink(file)
    else:
        call('systemctl reload-or-restart ocserv.service')
        counter = 0
        while True:
            # exit early when service runs
            if is_systemd_service_running("ocserv.service"):
                break
            sleep(0.250)
            if counter > 5:
                raise ConfigError('OpenConnect failed to start, check the logs for details')
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
