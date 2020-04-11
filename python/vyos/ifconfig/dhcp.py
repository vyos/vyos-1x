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

from vyos.dicts import FixedDict
from vyos.ifconfig.control import Control
from vyos.template import render


class _DHCP (Control):
    client_base = r'/var/lib/dhcp/dhclient_'

    def __init__(self, ifname, version, **kargs):
        super().__init__(**kargs)
        self.version = version
        self.file = {
            'ifname': ifname,
            'conf': self.client_base + ifname + '.' + version + 'conf',
            'pid': self.client_base + ifname + '.' + version + 'pid',
            'lease': self.client_base + ifname + '.' + version + 'leases',
        }

class _DHCPv4 (_DHCP):
    def __init__(self, ifname):
        super().__init__(ifname, '')
        self.options = FixedDict(**{
            'ifname': ifname,
            'hostname': '',
            'client_id': '',
            'vendor_class_id': ''
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

        render(self.file['conf'], 'dhcp-client/ipv4.tmpl' ,self.options)

        cmd = 'start-stop-daemon'
        cmd += ' --start'
        cmd += ' --oknodo'
        cmd += ' --quiet'
        cmd += ' --pidfile {pid}'
        cmd += ' --exec /sbin/dhclient'
        cmd += ' --'
        # now pass arguments to dhclient binary
        cmd += ' -4 -nw -cf {conf} -pf {pid} -lf {lease} {ifname}'
        return self._cmd(cmd.format(**self.file))

    def delete(self):
        """
        De-configure interface as DHCP clinet. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.dhcp.v4.delete()
        """
        if not os.path.isfile(self.file['pid']):
            self._debug_msg('No DHCP client PID found')
            return None

	# with open(self.file['pid'], 'r') as f:
	# 	pid = int(f.read())

        # stop dhclient, we need to call dhclient and tell it should release the
        # aquired IP address. tcpdump tells me:
        # 172.16.35.103.68 > 172.16.35.254.67: [bad udp cksum 0xa0cb -> 0xb943!] BOOTP/DHCP, Request from 00:50:56:9d:11:df, length 300, xid 0x620e6946, Flags [none] (0x0000)
        #  Client-IP 172.16.35.103
        #  Client-Ethernet-Address 00:50:56:9d:11:df
        #  Vendor-rfc1048 Extensions
        #    Magic Cookie 0x63825363
        #    DHCP-Message Option 53, length 1: Release
        #    Server-ID Option 54, length 4: 172.16.35.254
        #    Hostname Option 12, length 10: "vyos"
        #
        cmd = '/sbin/dhclient -cf {conf} -pf {pid} -lf {lease} -r {ifname}'
        self._cmd(cmd.format(**self.file))

        # cleanup old config files
        for name in ('conf', 'pid', 'lease'):
            if os.path.isfile(self.file[name]):
                os.remove(self.file[name])


class _DHCPv6 (_DHCP):
    def __init__(self, ifname):
        super().__init__(ifname, 'v6')
        self.options = FixedDict(**{
            'ifname': ifname,
            'dhcpv6_prm_only': False,
            'dhcpv6_temporary': False,
        })
        self.file.update({
            'accept_ra': f'/proc/sys/net/ipv6/conf/{ifname}/accept_ra',
        })

    def set(self):
        """
        Configure interface as DHCPv6 client. The dhclient binary is automatically
        started in background!

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.set_dhcpv6()
        """

        # better save then sorry .. should be checked in interface script
        # but if you missed it we are safe!
        if self.options['dhcpv6_prm_only'] and self.options['dhcpv6_temporary']:
            raise Exception(
                'DHCPv6 temporary and parameters-only options are mutually exclusive!')

        render(self.file['conf'], 'dhcp-client/ipv6.tmpl', self.options)

        # no longer accept router announcements on this interface
        self._write_sysfs(self.file['accept_ra'], 0)

        # assemble command-line to start DHCPv6 client (dhclient)
        cmd = 'start-stop-daemon'
        cmd += ' --start'
        cmd += ' --oknodo'
        cmd += ' --quiet'
        cmd += ' --pidfile {pid}'
        cmd += ' --exec /sbin/dhclient'
        cmd += ' --'
        # now pass arguments to dhclient binary
        cmd += ' -6 -nw -cf {conf} -pf {pid} -lf {lease}'
        # add optional arguments
        if self.options['dhcpv6_prm_only']:
            cmd += ' -S'
        if self.options['dhcpv6_temporary']:
            cmd += ' -T'
        cmd += ' {ifname}'

        return self._cmd(cmd.format(**self.file))

    def delete(self):
        """
        De-configure interface as DHCPv6 clinet. All auto generated files like
        pid, config and lease will be removed.

        Example:

        >>> from vyos.ifconfig import Interface
        >>> j = Interface('eth0')
        >>> j.del_dhcpv6()
        """
        if not os.path.isfile(self.file['pid']):
            self._debug_msg('No DHCPv6 client PID found')
            return None

        # with open(self.file['pid'], 'r') as f:
        # 	pid = int(f.read())

        # stop dhclient
        cmd = 'start-stop-daemon'
        cmd += ' --start'
        cmd += ' --oknodo'
        cmd += ' --quiet'
        cmd += ' --pidfile {pid}'
        self._cmd(cmd.format(**self.file))

        # accept router announcements on this interface
        self._write_sysfs(self.options['accept_ra'], 1)

        # cleanup old config files
        for name in ('conf', 'pid', 'lease'):
            if os.path.isfile(self.file[name]):
                os.remove(self.file[name])


class DHCP (object):
    def __init__(self, ifname):
        self.v4 = _DHCPv4(ifname)
        self.v6 = _DHCPv6(ifname)
