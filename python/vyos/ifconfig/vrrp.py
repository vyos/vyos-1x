# Copyright 2019-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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
import json
import signal

from time import time
from tabulate import tabulate

from vyos.configquery import ConfigTreeQuery
from vyos.utils.convert import seconds_to_human
from vyos.utils.file import read_file
from vyos.utils.file import wait_for_file_write_complete
from vyos.utils.process import process_running

class VRRPError(Exception):
    pass

class VRRPNoData(VRRPError):
    pass

class VRRP(object):
    _vrrp_prefix = '00:00:5E:00:01:'
    location = {
        'pid':      '/run/keepalived/keepalived.pid',
        'fifo':     '/run/keepalived/keepalived_notify_fifo',
        'state':    '/tmp/keepalived.data',
        'stats':    '/tmp/keepalived.stats',
        'json':     '/tmp/keepalived.json',
        'daemon':   '/etc/default/keepalived',
        'config':   '/run/keepalived/keepalived.conf',
    }

    _signal = {
        'state':  signal.SIGUSR1,
        'stats':  signal.SIGUSR2,
        'json':   signal.SIGRTMIN + 2,
    }

    _name = {
        'state': 'information',
        'stats': 'statistics',
        'json':  'data',
    }

    state = {
        0: 'INIT',
        1: 'BACKUP',
        2: 'MASTER',
        3: 'FAULT',
        # UNKNOWN
    }

    def __init__(self,ifname):
        self.ifname = ifname

    def enabled(self):
        return self.ifname in self.active_interfaces()

    @classmethod
    def active_interfaces(cls):
        if not os.path.exists(cls.location['pid']):
            return []
        data = cls.collect('json')
        return [group['data']['ifp_ifname'] for group in json.loads(data)]

    @classmethod
    def decode_state(cls, code):
        return cls.state.get(code,'UNKNOWN')

    # used in conf mode
    @classmethod
    def is_running(cls):
        if not os.path.exists(cls.location['pid']):
            return False
        return process_running(cls.location['pid'])

    @classmethod
    def collect(cls, what):
        fname = cls.location[what]
        try:
            # send signal to generate the configuration file
            pid = read_file(cls.location['pid'])
            wait_for_file_write_complete(fname,
              pre_hook=(lambda: os.kill(int(pid), cls._signal[what])),
              timeout=30)

            return read_file(fname)
        except OSError:
            # raised by vyos.utils.file.read_file
            raise VRRPNoData("VRRP data is not available (wait time exceeded)")
        except FileNotFoundError:
            raise VRRPNoData("VRRP data is not available (process not running or no active groups)")
        except Exception:
            name = cls._name[what]
            raise VRRPError(f'VRRP {name} is not available')
        finally:
            if os.path.exists(fname):
                os.remove(fname)

    @classmethod
    def disabled(cls):
        disabled = []
        base = ['high-availability', 'vrrp']
        conf = ConfigTreeQuery()
        if conf.exists(base):
            # Read VRRP configuration directly from CLI
            vrrp_config_dict = conf.get_config_dict(base, key_mangling=('-', '_'),
                                                    get_first_key=True)

            # add disabled groups to the list
            if 'group' in vrrp_config_dict:
                for group, group_config in vrrp_config_dict['group'].items():
                    if 'disable' not in group_config:
                        continue
                    disabled.append([group, group_config['interface'], group_config['vrid'], 'DISABLED', ''])

        # return list with disabled instances
        return disabled

    @classmethod
    def format(cls, data):
        headers = ["Name", "Interface", "VRID", "State", "Priority", "Last Transition"]
        groups = []

        data = json.loads(data)
        for group in data:
            data = group['data']

            name = data['iname']
            intf = data['ifp_ifname']
            vrid = data['vrid']
            state = cls.decode_state(data["state"])
            priority = data['effective_priority']

            since = int(time() - float(data['last_transition']))
            last = seconds_to_human(since)

            groups.append([name, intf, vrid, state, priority, last])

        # add to the active list disabled instances
        groups.extend(cls.disabled())
        return(tabulate(groups, headers))
