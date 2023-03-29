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

from time import time
from datetime import datetime
from functools import reduce
from tabulate import tabulate

from vyos.ifconfig import Control

class Operational(Control):
    """
    A class able to load Interface statistics
    """

    cache_magic = 'XYZZYX'

    _stat_names = {
        'rx': ['bytes', 'packets', 'errors', 'dropped', 'overrun', 'mcast'],
        'tx': ['bytes', 'packets', 'errors', 'dropped', 'carrier', 'collisions'],
    }

    _stats_dir = {
        'rx': ['rx_bytes', 'rx_packets', 'rx_errors', 'rx_dropped', 'rx_over_errors', 'multicast'],
        'tx': ['tx_bytes', 'tx_packets', 'tx_errors', 'tx_dropped', 'tx_carrier_errors', 'collisions'],
    }

    # a list made of the content of _stats_dir['rx'] + _stats_dir['tx']
    _stats_all = reduce(lambda x, y: x+y, _stats_dir.values())

    # this is not an interface but will be able to be controlled like one
    _sysfs_get = {
        'oper_state':{
            'location': '/sys/class/net/{ifname}/operstate',
        },
    }


    @classmethod
    def cachefile (cls, ifname):
        # the file where we are saving the counters
        return f'/var/run/vyatta/{ifname}.stats'


    def __init__(self, ifname):
        """
        Operational provide access to the counters of an interface
        It behave like an interface when it comes to access sysfs

        interface is an instance of the interface for which we want
        to look at (a subclass of Interface, such as EthernetIf)
        """

        # add a self.config to minic Interface behaviour and make
        # coding similar. Perhaps part of class Interface could be
        # moved into a shared base class.
        self.config = {
            'ifname': ifname,
            'create': False,
            'debug': False,
        }
        super().__init__(**self.config)
        self.ifname = ifname

        # adds all the counters of an interface
        for stat in self._stats_all:
            self._sysfs_get[stat] = {
                'location': '/sys/class/net/{ifname}/statistics/'+stat,
            }

    def get_state(self):
        """
        Get interface operational state

        Example:
        >>> from vyos.ifconfig import Interface
        >>> Interface('eth0').operational.get_sate()
        'up'
        """
        # https://www.kernel.org/doc/Documentation/ABI/testing/sysfs-class-net
        # "unknown", "notpresent", "down", "lowerlayerdown", "testing", "dormant", "up"
        return self.get_interface('oper_state')

    @classmethod
    def strtime (cls, epoc):
        """
        represent an epoc/unix date in the format used by operation commands
        """
        return datetime.fromtimestamp(epoc).strftime("%a %b %d %R:%S %Z %Y")

    def save_counters(self, stats):
        """
        record the provided stats to a file keeping vyatta compatibility
        """

        with open(self.cachefile(self.ifname), 'w') as f:
            f.write(self.cache_magic)
            f.write('\n')
            f.write(str(int(time())))
            f.write('\n')
            for k,v in stats.items():
                if v:
                    f.write(f'{k},{v}\n')

    def load_counters(self):
        """
        load the stats from a file keeping vyatta compatibility
        return a dict() with the value for each interface counter for the cache
        """
        ifname = self.config['ifname']

        stats = {}
        no_stats = {}
        for name in self._stats_all:
            stats[name] = 0
            no_stats[name] = 0

        try:
            with open(self.cachefile(self.ifname),'r') as f:
                magic = f.readline().strip()
                if magic != self.cache_magic:
                    print(f'bad magic {ifname}')
                    return no_stats
                stats['timestamp'] = f.readline().strip()
                for line in f:
                    k, v = line.split(',')
                    stats[k] = int(v)
            return stats
        except IOError:
            return no_stats

    def clear_counters(self):
        stats = self.get_stats()
        for counter, value in stats.items():
            stats[counter] = value
        self.save_counters(stats)

    def reset_counters(self):
        try:
            os.remove(self.cachefile(self.ifname))
        except FileNotFoundError:
            pass

    def get_stats(self):
        """ return a dict() with the value for each interface counter """
        stats = {}
        for counter in self._stats_all:
            stats[counter] = int(self.get_interface(counter))
        return stats

    def formated_stats(self, indent=4):
        tabs = []
        stats = self.get_stats()
        for rtx in self._stats_dir:
            tabs.append([f'{rtx.upper()}:', ] + [_ for _ in self._stat_names[rtx]])
            tabs.append(['', ] + [stats[_] for _ in self._stats_dir[rtx]])

        s = tabulate(
            tabs,
            stralign="right",
            numalign="right",
            tablefmt="plain"
        )

        p = ' '*indent
        return f'{p}' + s.replace('\n', f'\n{p}')
