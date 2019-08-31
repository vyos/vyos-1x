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

import sys
import re
import os
import jinja2
import syslog as sl

import vyos.config
import vyos.defaults

from vyos import ConfigError


ra_conn_name = "remote-access"
charon_conf_file = "/etc/strongswan.d/charon.conf"
ipsec_secrets_flie = "/etc/ipsec.secrets"
ipsec_ra_conn_file = "/etc/ipsec.d/tunnels/"+ra_conn_name
ipsec_conf_flie = "/etc/ipsec.conf"
ca_cert_path = '/etc/ipsec.d/cacerts'
server_cert_path = '/etc/ipsec.d/certs'
server_key_path = '/etc/ipsec.d/private'
delim_ipsec_l2tp_begin = "### VyOS L2TP VPN Begin ###"
delim_ipsec_l2tp_end = "### VyOS L2TP VPN End ###"

l2pt_ipsec_conf = '''
{{delim_ipsec_l2tp_begin}}
include {{ipsec_ra_conn_file}}
{{delim_ipsec_l2tp_end}}
'''

l2pt_ipsec_secrets_conf = '''
{{delim_ipsec_l2tp_begin}}
{% if ipsec_l2tp_auth_mode == 'pre-shared-secret' %}
{{outside_addr}} %any : PSK "{{ipsec_l2tp_secret}}"
{% elif ipsec_l2tp_auth_mode == 'x509' %}
: RSA {{server_key_file_copied}}
{% endif%}
{{delim_ipsec_l2tp_end}}
'''

l2tp_ipsec_ra_conn_conf = '''
{{delim_ipsec_l2tp_begin}}
conn {{ra_conn_name}}
  type=transport
  left={{outside_addr}}
  leftsubnet=%dynamic[/1701]
  rightsubnet=%dynamic
  mark_in=%unique
  auto=add
  ike=aes256-sha1-modp1024,3des-sha1-modp1024,3des-sha1-modp1024!
  dpddelay=15
  dpdtimeout=45
  dpdaction=clear
  esp=aes256-sha1,3des-sha1!
  rekey=no
{% if ipsec_l2tp_auth_mode == 'pre-shared-secret' %}
  authby=secret
  leftauth=psk
  rightauth=psk
{% elif ipsec_l2tp_auth_mode == 'x509' %}
  authby=rsasig
  leftrsasigkey=%cert
  rightrsasigkey=%cert
  rightca=%same
  leftcert={{server_cert_file_copied}}
{% endif %}
  ikelifetime={{ipsec_l2tp_ike_lifetime}}
  keylife={{ipsec_l2tp_lifetime}}
{{delim_ipsec_l2tp_end}}
'''

def get_config():
    config = vyos.config.Config()
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

### ipsec secret l2tp
def write_ipsec_secrets(c):
  tmpl = jinja2.Template(l2pt_ipsec_secrets_conf, trim_blocks=True)
  l2pt_ipsec_secrets_txt = tmpl.render(c)
  old_umask = os.umask(0o077)
  open(ipsec_secrets_flie,'w').write(l2pt_ipsec_secrets_txt)
  os.umask(old_umask)
  sl.syslog(sl.LOG_NOTICE, ipsec_secrets_flie + ' written')

### ipsec remote access connection config
def write_ipsec_ra_conn(c):
  tmpl = jinja2.Template(l2tp_ipsec_ra_conn_conf, trim_blocks=True)
  ipsec_ra_conn_txt = tmpl.render(c)
  old_umask = os.umask(0o077)
  open(ipsec_ra_conn_file,'w').write(ipsec_ra_conn_txt)
  os.umask(old_umask)
  sl.syslog(sl.LOG_NOTICE, ipsec_ra_conn_file + ' written')

### Remove config from file by delimiter
def remove_confs(delim_begin, delim_end, conf_file):
    os.system("sed -i '/"+delim_begin+"/,/"+delim_end+"/d' "+conf_file)


### Append "include /path/to/ra_conn" to ipsec conf file
def append_ipsec_conf(c):
    tmpl = jinja2.Template(l2pt_ipsec_conf, trim_blocks=True)
    l2pt_ipsec_conf_txt = tmpl.render(c)
    old_umask = os.umask(0o077)
    open(ipsec_conf_flie,'a').write(l2pt_ipsec_conf_txt)
    os.umask(old_umask)
    sl.syslog(sl.LOG_NOTICE, ipsec_conf_flie + ' written')

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
      ret = os.system('cp -f '+file_path+' '+dts_path)
      if ret:
         raise ConfigError("L2TP VPN configuration error: Cannot copy "+file_path)
      else:
        sl.syslog(sl.LOG_NOTICE, file_path + ' copied to '+dts_path)

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
    tmpl_path = os.path.join(vyos.defaults.directories["data"], "templates", "ipsec")
    fs_loader = jinja2.FileSystemLoader(tmpl_path)
    env = jinja2.Environment(loader=fs_loader)


    charon_conf_tmpl = env.get_template("charon.tmpl")
    charon_conf = charon_conf_tmpl.render(data)

    with open(charon_conf_file, 'w') as f:
        f.write(charon_conf)

    if data["ipsec_l2tp"]:
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_conf_flie)
        write_ipsec_secrets(data)
        write_ipsec_ra_conn(data)
        append_ipsec_conf(data)
    else:
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_ra_conn_file)
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_secrets_flie)
        remove_confs(delim_ipsec_l2tp_begin, delim_ipsec_l2tp_end, ipsec_conf_flie)

def apply(data):
    # Do nothing
    # StrongSWAN should only be restarted when actual tunnels are configured
    # Restart ipsec for l2tp
    os.system("ipsec restart >&/dev/null")

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
