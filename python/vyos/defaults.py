# Copyright 2018-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

base_dir = '/usr/libexec/vyos/'

directories = {
  'base' : base_dir,
  'data' : '/usr/share/vyos/',
  'conf_mode' : f'{base_dir}/conf_mode',
  'op_mode' : f'{base_dir}/op_mode',
  'services' : f'{base_dir}/services',
  'config' : '/opt/vyatta/etc/config',
  'migrate' : '/opt/vyatta/etc/config-migrate/migrate',
  'activate' : f'{base_dir}/activate',
  'log' : '/var/log/vyatta',
  'templates' : '/usr/share/vyos/templates/',
  'certbot' : '/config/auth/letsencrypt',
  'api_schema': f'{base_dir}/services/api/graphql/graphql/schema/',
  'api_client_op': f'{base_dir}/services/api/graphql/graphql/client_op/',
  'api_templates': f'{base_dir}/services/api/graphql/session/templates/',
  'vyos_udev_dir' : '/run/udev/vyos',
  'isc_dhclient_dir' : '/run/dhclient',
  'dhcp6_client_dir' : '/run/dhcp6c',
  'vyos_configdir' : '/opt/vyatta/config',
  'completion_dir' : f'{base_dir}/completion'
}

config_status = '/tmp/vyos-config-status'
api_config_state = '/run/http-api-state'

cfg_group = 'vyattacfg'

cfg_vintage = 'vyos'

commit_lock = os.path.join(directories['vyos_configdir'], '.lock')

component_version_json = os.path.join(directories['data'], 'component-versions.json')

config_default = os.path.join(directories['data'], 'config.boot.default')

rt_symbolic_names = {
  # Standard routing tables for Linux & reserved IDs for VyOS
  'default': 253, # Confusingly, a final fallthru, not the default. 
  'main': 254,    # The actual global table used by iproute2 unless told otherwise. 
  'local': 255,   # Special kernel loopback table.
}

rt_global_vrf = rt_symbolic_names['main']
rt_global_table = rt_symbolic_names['main']
