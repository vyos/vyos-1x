# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.configverify import verify_dhcpv6
from vyos.dicts import FixedDict
from vyos.ifconfig.control import Control
from vyos.template import render

class _DHCPv4 (Control):
    def __init__(self, ifname):
        super().__init__()
        config_base = r'/var/lib/dhcp/dhclient_'
        self.options = FixedDict(**{
            'ifname': ifname,
            'hostname': '',
            'client_id': '',
            'vendor_class_id': '',
            'conf_file': config_base + f'{ifname}.conf',
            'options_file': config_base + f'{ifname}.options',
            'pid_file': config_base + f'{ifname}.pid',
            'lease_file': config_base + f'{ifname}.leases',
        })

    # replace dhcpv4/v6 with systemd.networkd?
    def set(self):
        """
        Configure interface as DHCP client. The dhclient binary is automatically
        started in background!

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.dhcp.v4.set()
        """
        if not self.options['hostname']:
            # read configured system hostname.
            # maybe change to vyos hostd client ???
            with open('/etc/hostname', 'r') as f:
                self.options['hostname'] = f.read().rstrip('\n')

        render(self.options['options_file'], 'dhcp-client/daemon-options.tmpl', self.options)
        render(self.options['conf_file'], 'dhcp-client/ipv4.tmpl', self.options)

        return self._cmd('systemctl restart dhclient@{ifname}.service'.format(**self.options))

    def delete(self):
        """
        De-configure interface as DHCP clinet. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.dhcp.v4.delete()
        """
        if not os.path.isfile(self.options['pid_file']):
            self._debug_msg('No DHCP client PID found')
            return None

        self._cmd('systemctl stop dhclient@{ifname}.service'.format(**self.options))

        # cleanup old config files
        for name in ('conf_file', 'options_file', 'pid_file', 'lease_file'):
            if os.path.isfile(self.options[name]):
                os.remove(self.options[name])

class _DHCPv6 (Control):
    def __init__(self, ifname):
        super().__init__()
        self.options = {'ifname' : ifname}
        self._config = f'/run/dhcp6c/dhcp6c.{ifname}.conf'

    def set(self):
        """
        Configure interface as DHCPv6 client. The client is automatically
        started in background when address is configured as DHCP.

        Example:
        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.dhcp.v6.set()
        """

        # better save then sorry .. should be checked in interface script but if you
        # missed it we are safe!
        verify_dhcpv6(self.options)

        render(self._config, 'dhcp-client/ipv6.tmpl', self.options, trim_blocks=True)
        return self._cmd('systemctl restart dhcp6c@{ifname}.service'.format(
            **self.options))

    def delete(self):
        """
        De-configure interface as DHCPv6 client. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.dhcp.v6.delete()
        """
        self._cmd('systemctl stop dhcp6c@{ifname}.service'.format(**self.options))

        # cleanup old config files
        if os.path.isfile(self._config):
            os.remove(self._config)

class DHCP(object):
    def __init__(self, ifname):
        self.v4 = _DHCPv4(ifname)
        self.v6 = _DHCPv6(ifname)
