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


directories = {
  "data": "/usr/share/vyos/",
  "conf_mode": "/usr/libexec/vyos/conf_mode",
  "config": "/opt/vyatta/etc/config",
  "current": "/opt/vyatta/etc/config-migrate/current",
  "migrate": "/opt/vyatta/etc/config-migrate/migrate",
}

cfg_group = 'vyattacfg'

cfg_vintage = 'vyatta'

commit_lock = '/opt/vyatta/config/.lock'

https_data = {
    'listen_address' : [ '127.0.0.1' ]
}

api_data = {
    'listen_address' : '127.0.0.1',
    'port' : '8080',
    'strict' : 'false',
    'debug' : 'false',
    'api_keys' : [ {"id": "testapp", "key": "qwerty"} ]
}
