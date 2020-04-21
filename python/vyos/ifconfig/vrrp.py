# Copyright 2019 VyOS maintainers and contributors <maintainers@vyos.io>
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
from time import sleep

from tabulate import tabulate

from vyos import airbag
from vyos import util


class VRRPError(Exception):
    pass

class VRRP(object):
    _vrrp_prefix = '00:00:5E:00:01:'
    location = {
        'pid':      '/run/keepalived.pid',
        'fifo':     '/run/keepalived_notify_fifo',
        'state':    '/tmp/keepalived.data',
        'stats':    '/tmp/keepalived.stats',
        'json':     '/tmp/keepalived.json',
        'daemon':   '/etc/default/keepalived',
        'config':   '/etc/keepalived/keepalived.conf',
        'vyos':     '/run/keepalived_config.dict',
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
        return util.process_running(cls.location['pid'])

    @classmethod
    def collect(cls, what):
        fname = cls.location[what]
        try:
            # send signal to generate the configuration file
            pid = util.read_file(cls.location['pid'])
            os.kill(int(pid), cls._signal[what])

            # shoud look for file size change ?
            sleep(0.2)
            return util.read_file(fname)
        except Exception:
            name = cls._name[what]
            raise VRRPError(f'VRRP {name} is not available')
        finally:
            if os.path.exists(fname):
                os.remove(fname)

    @classmethod
    def disabled(cls):
        if not os.path.exists(cls.location['vyos']):
            return []

        disabled = []
        config = json.loads(util.read_file(cls.location['vyos']))

        # add disabled groups to the list
        for group in config['vrrp_groups']:
            if group['disable']:
                disabled.append(
                    [group['name'], group['interface'], group['vrid'], 'DISABLED', ''])

        # return list with disabled instances
        return disabled

    @classmethod
    def format (cls, data):
        headers = ["Name", "Interface", "VRID", "State", "Last Transition"]
        groups = []

        data = json.loads(data)
        for group in data:
            data = group['data']

            name = data['iname']
            intf = data['ifp_ifname']
            vrid = data['vrid']
            state = cls.decode_state(data["state"])

            since = int(time() - float(data['last_transition']))
            last = util.seconds_to_human(since)

            groups.append([name, intf, vrid, state, last])

        # add to the active list disabled instances
        groups.extend(cls.disabled())
        return(tabulate(groups, headers))

