# Copyright 2018 VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import os

env_file = os.path.join(os.environ.get("vyos_data_dir", "/usr/share/vyos/"),"vyos.env")

env = {}
with open(env_file, 'r') as envfile:
    for line in envfile:
        line = line.strip().replace(' ', '').replace('\t', '')
        split = line.split('=')
        if len(split) != 2:
            continue
        key, value = split
        env[key] = os.environ.get(key, value)

directories = {
  "data": env.get("vyos_data_dir", "/usr/share/vyos/"),
  "conf_mode": env.get("vyos_conf_scripts_dir","/usr/libexec/vyos/conf_mode"),
  "config": os.path.join(env.get("vyatta_sysconfdir", "/opt/vyatta/etc"),"config"),
  "current": os.path.join(env.get("vyatta_sysconfdir", "/opt/vyatta/etc"), "config-migrate/current"),
  "migrate": os.path.join(env.get("vyatta_sysconfdir", "/opt/vyatta/etc"), "config-migrate/migrate"),
  "log": env.get("vyatta_log", "/var/log/vyatta"),
}

cfg_group = 'vyattacfg'

cfg_vintage = 'vyatta'

commit_lock = os.path.join(env.get('vyatta_configdir', '/opt/vyatta/config'), '.lock')

version_file = os.path.join(directories['data'], 'component-versions.json')

https_data = {
    'listen_addresses' : { '*': ['_'] }
}

api_data = {
    'listen_address' : '127.0.0.1',
    'port' : '8080',
    'strict' : 'false',
    'debug' : 'false',
    'api_keys' : [ {"id": "testapp", "key": "qwerty"} ]
}

vyos_cert_data = {
    "conf": "/etc/nginx/snippets/vyos-cert.conf",
    "crt": "/etc/ssl/certs/vyos-selfsigned.crt",
    "key": "/etc/ssl/private/vyos-selfsign",
    "lifetime": "365",
}
