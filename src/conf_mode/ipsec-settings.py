#!/usr/bin/env python3
#
# Copyright (C) 2018-2020 VyOS maintainers and contributors
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

from time import sleep
from sys import exit

from vyos.config import Config
from vyos import ConfigError
from vyos.util import call
from vyos.template import render

from vyos import airbag
airbag.enable()

ra_conn_name = "remote-access"
charon_conf_file = "/etc/strongswan.d/charon.conf"
ipsec_secrets_file = "/etc/ipsec.secrets"
ipsec_ra_conn_dir = "/etc/ipsec.d/tunnels/"
ipsec_ra_conn_file = ipsec_ra_conn_dir + ra_conn_name
ipsec_conf_file = "/etc/ipsec.conf"
ca_cert_path = "/etc/ipsec.d/cacerts"
server_cert_path = "/etc/ipsec.d/certs"
server_key_path = "/etc/ipsec.d/private"
delim_ipsec_l2tp_begin = "### VyOS L2TP VPN Begin ###"
delim_ipsec_l2tp_end = "### VyOS L2TP VPN End ###"
charon_pidfile = "/var/run/charon.pid"

def get_config(config=None):
    if config:
        config = config
    else:
        config = Config()
    data = {"install_routes": "yes"}

    if config.exists("vpn ipsec options disable-route-autoinstall"):
        data["install_routes"] = "no"

    if config.exists("vpn ipsec ipsec-interfaces interface"):
        data["ipsec_interfaces"] = config.return_values("vpn ipsec ipsec-interfaces interface")

    # Init config variables
    data["delim_ipsec_l2tp_begin"] = delim_ipsec_l2tp_begin
    data["delim_ipsec_l2tp_end"] = delim_ipsec_l2tp_end
    data["ipsec_ra_conn_file"] = ipsec_ra_conn_file
    data["ra_conn_name"] = ra_conn_name
    # Get l2tp ipsec settings
    data["ipsec_l2tp"] = False
    conf_ipsec_command = "vpn l2tp remote-access ipsec-settings " #last space is useful
    if config.exists(conf_ipsec_command):
        data["ipsec_l2tp"] = True

        # Authentication params
        if config.exists(conf_ipsec_command + "authentication mode"):
            data["ipsec_l2tp_auth_mode"] = config.return_value(conf_ipsec_command + "authentication mode")
        if config.exists(conf_ipsec_command + "authentication pre-shared-secret"):
            data["ipsec_l2tp_secret"] = config.return_value(conf_ipsec_command + "authentication pre-shared-secret")

        # mode x509
        if config.exists(conf_ipsec_command + "authentication x509 ca-cert-file"):
            data["ipsec_l2tp_x509_ca_cert_file"] = config.return_value(conf_ipsec_command + "authentication x509 ca-cert-file")
        if config.exists(conf_ipsec_command + "authentication x509 crl-file"):
            data["ipsec_l2tp_x509_crl_file"] = config.return_value(conf_ipsec_command + "authentication x509 crl-file")
        if config.exists(conf_ipsec_command + "authentication x509 server-cert-file"):
            data["ipsec_l2tp_x509_server_cert_file"] = config.return_value(conf_ipsec_command + "authentication x509 server-cert-file")
            data["server_cert_file_copied"] = server_cert_path+"/"+re.search('\w+(?:\.\w+)*$', config.return_value(conf_ipsec_command + "authentication x509 server-cert-file")).group(0)
        if config.exists(conf_ipsec_command + "authentication x509 server-key-file"):
            data["ipsec_l2tp_x509_server_key_file"] = config.return_value(conf_ipsec_command + "authentication x509 server-key-file")
            data["server_key_file_copied"] = server_key_path+"/"+re.search('\w+(?:\.\w+)*$', config.return_value(conf_ipsec_command + "authentication x509 server-key-file")).group(0)
        if config.exists(conf_ipsec_command + "authentication x509 server-key-password"):
            data["ipsec_l2tp_x509_server_key_password"] = config.return_value(conf_ipsec_command + "authentication x509 server-key-password")

        # Common l2tp ipsec params
        if config.exists(conf_ipsec_command + "ike-lifetime"):
            data["ipsec_l2tp_ike_lifetime"] = config.return_value(conf_ipsec_command + "ike-lifetime")
        else:
            data["ipsec_l2tp_ike_lifetime"] = "3600"

        if config.exists(conf_ipsec_command + "lifetime"):
            data["ipsec_l2tp_lifetime"] = config.return_value(conf_ipsec_command + "lifetime")
        else:
            data["ipsec_l2tp_lifetime"] = "3600"

    if config.exists("vpn l2tp remote-access outside-address"):
        data['outside_addr'] = config.return_value('vpn l2tp remote-access outside-address')

    return data

def write_ipsec_secrets(c):
    if c.get("ipsec_l2tp_auth_mode") == "pre-shared-secret":
        secret_txt = "{0}\n{1} %any : PSK \"{2}\"\n{3}\n".format(delim_ipsec_l2tp_begin, c['outside_addr'], c['ipsec_l2tp_secret'], delim_ipsec_l2tp_end)
    elif c.get("ipsec_l2tp_auth_mode") == "x509":
        secret_txt = "{0}\n: RSA {1}\n{2}\n".format(delim_ipsec_l2tp_begin, c['server_key_file_copied'], delim_ipsec_l2tp_end)

    old_umask = os.umask(0o077)
    with open(ipsec_secrets_file, 'a+') as f:
        f.write(secret_txt)
    os.umask(old_umask)

def write_ipsec_conf(c):
    ipsec_confg_txt = "{0}\ninclude {1}\n{2}\n".format(delim_ipsec_l2tp_begin, ipsec_ra_conn_file, delim_ipsec_l2tp_end)

    old_umask = os.umask(0o077)
    with open(ipsec_conf_file, 'a+') as f:
        f.write(ipsec_confg_txt)
    os.umask(old_umask)

### Remove config from file by delimiter
def remove_confs(delim_begin, delim_end, conf_file):
    call("sed -i '/"+delim_begin+"/,/"+delim_end+"/d' "+conf_file)


### Checking certificate storage and notice if certificate not in /config directory
def check_cert_file_store(cert_name, file_path, dts_path):
    if not re.search('^\/config\/.+', file_path):
        print("Warning: \"" + file_path + "\" lies outside of /config/auth directory. It will not get preserved during image upgrade.")
    #Checking file existence
    if not os.path.isfile(file_path):
      raise ConfigError("L2TP VPN configuration error: Invalid "+cert_name+" \""+file_path+"\"")
    else:
      ### Cpy file to /etc/ipsec.d/certs/ /etc/ipsec.d/cacerts/
      # todo make check
      ret = call('cp -f '+file_path+' '+dts_path)
      if ret:
         raise ConfigError("L2TP VPN configuration error: Cannot copy "+file_path)

def verify(data):
    # l2tp ipsec check
    if data["ipsec_l2tp"]:
        # Checking dependecies for "authentication mode pre-shared-secret"
        if data.get("ipsec_l2tp_auth_mode") == "pre-shared-secret":
            if not data.get("ipsec_l2tp_secret"):
                raise ConfigError("pre-shared-secret required")
            if not data.get("outside_addr"):
                raise ConfigError("outside-address not defined")

        # Checking dependecies for "authentication mode x509"
        if data.get("ipsec_l2tp_auth_mode") == "x509":
            if not data.get("ipsec_l2tp_x509_server_key_file"):
                raise ConfigError("L2TP VPN configuration error: \"server-key-file\" not defined.")
            else:
                check_cert_file_store("server-key-file", data['ipsec_l2tp_x509_server_key_file'], server_key_path)

            if not data.get("ipsec_l2tp_x509_server_cert_file"):
                raise ConfigError("L2TP VPN configuration error: \"server-cert-file\" not defined.")
            else:
                check_cert_file_store("server-cert-file", data['ipsec_l2tp_x509_server_cert_file'], server_cert_path)

            if not data.get("ipsec_l2tp_x509_ca_cert_file"):
                raise ConfigError("L2TP VPN configuration error: \"ca-cert-file\" must be defined for X.509")
            else:
                check_cert_file_store("ca-cert-file", data['ipsec_l2tp_x509_ca_cert_file'], ca_cert_path)

        if not data.get('ipsec_interfaces'):
           raise ConfigError("L2TP VPN configuration error: \"vpn ipsec ipsec-interfaces\" must be specified.")

def generate(data):
    render(charon_conf_file, 'ipsec/charon.tmpl', data, trim_blocks=True)

    if data["ipsec_l2tp"]:
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_secrets_file)
        # old_umask = os.umask(0o077)
        # render(ipsec_secrets_file, 'ipsec/ipsec.secrets.tmpl', data, trim_blocks=True)
        # os.umask(old_umask)
        ## Use this method while IPSec CLI handler won't be overwritten to python
        write_ipsec_secrets(data)

        old_umask = os.umask(0o077)

        # Create tunnels directory if does not exist
        if not os.path.exists(ipsec_ra_conn_dir):
            os.makedirs(ipsec_ra_conn_dir)

        render(ipsec_ra_conn_file, 'ipsec/remote-access.tmpl', data, trim_blocks=True)
        os.umask(old_umask)

        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_conf_file)
        # old_umask = os.umask(0o077)
        # render(ipsec_conf_file, 'ipsec/ipsec.conf.tmpl', data, trim_blocks=True)
        # os.umask(old_umask)
        ## Use this method while IPSec CLI handler won't be overwritten to python
        write_ipsec_conf(data)

    else:
        if os.path.exists(ipsec_ra_conn_file):
            remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_ra_conn_file)
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_secrets_file)
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_conf_file)

def restart_ipsec():
    call('ipsec restart >&/dev/null')
    # counter for apply swanctl config
    counter = 10
    while counter <= 10:
        if os.path.exists(charon_pidfile):
            call('swanctl -q >&/dev/null')
            break
        counter -=1
        sleep(1)
        if counter == 0:
            raise ConfigError('VPN configuration error: IPSec is not running.')

def apply(data):
    # Restart IPSec daemon
    restart_ipsec()

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
