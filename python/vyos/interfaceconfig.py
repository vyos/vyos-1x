#!/usr/bin/python3

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

import sys
import os
import re
import json
import socket
import subprocess
import ipaddress

dhclient_conf_dir = r'/var/lib/dhcp/dhclient_'

class Interface:
    def __init__(self, ifname=None, type=None):
        """
        Create instance of an IP interface

        Example:

        from vyos.interfaceconfig import Interface
        i = Interface('br111', type='bridge')
        """

        if not ifname:
            raise Exception("interface name required")

        if not os.path.exists('/sys/class/net/{0}'.format(ifname)) and not type:
            raise Exception("interface {0} not found".format(str(ifname)))

        if not os.path.exists('/sys/class/net/{0}'.format(ifname)):
            try:
                cmd = 'ip link add dev "{}" type "{}"'.format(ifname, type)
                self._cmd(cmd)
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                if "Operation not supported" in str(e.output.decode()):
                    print(str(e.output.decode()))
                    sys.exit(0)

        self._ifname = str(ifname)

    @property
    def remove(self):
        """
        Remove system interface

        Example:

        from vyos.interfaceconfig import Interface
        i = Interface('br111', type='bridge')
        i.remove
        """

        # NOTE (Improvement):
        # after interface removal no other commands should be allowed
        # to be called and instead should raise an Exception:

        cmd = 'ip link del dev "{}"'.format(self._ifname)
        self._cmd(cmd)


    def _cmd(self, command):
        process = subprocess.Popen(command,stdout=subprocess.PIPE, shell=True)
        proc_stdout = process.communicate()[0].strip()
        pass


    @property
    def mtu(self):
        """
        Get/set interface mtu in bytes.

        Example:

        from vyos.interfaceconfig import Interface
        mtu = Interface('ens192').mtu
        print(mtu)
        """

        mtu = 0
        with open('/sys/class/net/{0}/mtu'.format(self._ifname), 'r') as f:
            mtu = f.read().rstrip('\n')
        return mtu


    @mtu.setter
    def mtu(self, mtu=None):
        """
        Get/set interface mtu in bytes.

        Example:

        from vyos.interfaceconfig import Interface
        Interface('ens192').mtu = 1400
        """

        if mtu < 68 or mtu > 9000:
            raise ValueError('Invalid MTU size: "{}"'.format(mru))

        with open('/sys/class/net/{0}/mtu'.format(self._ifname), 'w') as f:
            f.write(str(mtu))


    @property
    def mac(self):
        """
        Get/set interface mac address

        Example:

        from vyos.interfaceconfig import Interface
        mac = Interface('ens192').mac
        """
        address = ''
        with open('/sys/class/net/{0}/address'.format(self._ifname), 'r') as f:
            address = f.read().rstrip('\n')
        return address


    @mac.setter
    def mac(self, mac=None):
        """
        Get/set interface mac address

        Example:

        from vyos.interfaceconfig import Interface
        Interface('ens192').mac = '00:90:43:fe:fe:1b'
        """
        # a mac address consits out of 6 octets
        octets = len(mac.split(':'))
        if octets != 6:
            raise ValueError('wrong number of MAC octets: {} '.format(octets))

        # validate against the first mac address byte if it's a multicast address
        if int(mac.split(':')[0]) & 1:
            raise ValueError('{} is a multicast MAC address'.format(mac))

        # overall mac address is not allowed to be 00:00:00:00:00:00
        if sum(int(i, 16) for i in mac.split(':')) == 0:
            raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

        # check for VRRP mac address
        if mac.split(':')[0] == '0' and addr.split(':')[1] == '0' and mac.split(':')[2] == '94' and mac.split(':')[3] == '0' and mac.split(':')[4] == '1':
            raise ValueError('{} is a VRRP MAC address'.format(mac))

        # Assemble command executed on system. Unfortunately there is no way
        # of altering the MAC address via sysfs
        cmd = 'ip link set dev "{}" address "{}"'.format(self._ifname, mac)
        self._cmd(cmd)


    @property
    def ifalias(self):
        """
        Get/set interface alias name

        Example:

        from vyos.interfaceconfig import Interface
        alias = Interface('ens192').ifalias
        """

        alias = ''
        with open('/sys/class/net/{0}/ifalias'.format(self._ifname), 'r') as f:
            alias = f.read().rstrip('\n')
        return alias


    @ifalias.setter
    def ifalias(self, ifalias=None):
        """
        Get/set interface alias name

        Example:

        from vyos.interfaceconfig import Interface
        Interface('ens192').ifalias = 'VyOS upstream interface'

        to clear interface alias e.g. delete it use:

        Interface('ens192').ifalias = ''
        """

        # clear interface alias
        if not ifalias:
            ifalias = '\0'

        with open('/sys/class/net/{0}/ifalias'.format(self._ifname), 'w') as f:
            f.write(str(ifalias))


    def up(self):
        """
        Bring interface up

        Example:

        from vyos.interfaceconfig import Interface
        i = Interface('br100', type='bridge')
        i.up()
        """

        # Assemble command executed on system. Unfortunately there is no way
        # to up/down an interface via sysfs
        cmd = 'ip link set dev "{}" up'.format(self._ifname)
        self._cmd(cmd)


    def down(self):
        """
        Bring interface down

        Example:

        from vyos.interfaceconfig import Interface
        i = Interface('br100', type='bridge')
        i.down()
        """

        # Assemble command executed on system. Unfortunately there is no way
        # to up/down an interface via sysfs
        cmd = 'ip link set dev "{}" down'.format(self._ifname)
        self._cmd(cmd)


    def _debug(self, e=None):
        """
        export DEBUG=1 to see debug messages
        """
        if os.getenv('DEBUG') == '1':
            if e:
                print ("Exception raised:\ncommand: {0}\nerror code: {1}\nsubprocess output: {2}".format(
                    e.cmd, e.returncode, e.output.decode()))
            return True
        return False


    def get_addr(self, ret_prefix=None):
        """
        universal: reads all IPs assigned to an interface and returns it in a list,
        or None if no IP address is assigned to the interface. Also may return
        in prefix format if set ret_prefix
        """
        ips = []
        try:
            ret = subprocess.check_output(
                ['ip -j addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            j = json.loads(ret)
            for i in j:
                if len(i) != 0:
                    for addr in i['addr_info']:
                        if ret_prefix:
                            ips.append(
                                addr['local'] + "/" + str(addr['prefixlen']))
                        else:
                            ips.append(addr['local'])
            return ips
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def get_ipv4_addr(self):
        """
        reads all IPs assigned to an interface and returns it in a list,
        or None if no IP address is assigned to the interface
        """
        ips = []
        try:
            ret = subprocess.check_output(
                ['ip -j -4 addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            j = json.loads(ret)
            for i in j:
                if len(i) != 0:
                    for addr in i['addr_info']:
                        ips.append(addr['local'])
            return ips
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def get_ipv6_addr(self):
        """
        reads all IPs assigned to an interface and returns it in a list,
        or None if no IP address is assigned to the interface
        """
        ips = []
        try:
            ret = subprocess.check_output(
                ['ip -j -6 addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            j = json.loads(ret)
            for i in j:
                if len(i) != 0:
                    for addr in i['addr_info']:
                        ips.append(addr['local'])
            return ips
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def add_addr(self, ipaddr=[]):
        """
            universal: add ipv4/ipv6 addresses on the interface
        """
        for ip in ipaddr:
            proto = '-4'
            if ipaddress.ip_address(ip.split(r'/')[0]).version == 6:
                proto = '-6'

            try:
                ret = subprocess.check_output(
                    ['ip ' + proto + ' address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    def del_addr(self, ipaddr=[]):
        """
            universal: delete ipv4/ipv6 addresses on the interface
        """
        for ip in ipaddr:
            proto = '-4'
            if ipaddress.ip_address(ip.split(r'/')[0]).version == 6:
                proto = '-6'
            try:
                ret = subprocess.check_output(
                    ['ip ' + proto + ' address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    def add_ipv4_addr(self, ipaddr=[]):
        """
        add addresses on the interface
        """
        for ip in ipaddr:
            try:
                ret = subprocess.check_output(
                    ['ip -4 address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    def del_ipv4_addr(self, ipaddr=[]):
        """
        delete addresses on the interface
        """
        for ip in ipaddr:
            try:
                ret = subprocess.check_output(
                    ['ip -4 address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    def add_ipv6_addr(self, ipaddr=[]):
        """
        add addresses on the interface
        """
        for ip in ipaddr:
            try:
                ret = subprocess.check_output(
                    ['ip -6 address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    def del_ipv6_addr(self, ipaddr=[]):
        """
        delete addresses on the interface
        """
        for ip in ipaddr:
            try:
                ret = subprocess.check_output(
                    ['ip -6 address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
                return None
        return True

    # replace dhcpv4/v6 with systemd.networkd?
    def set_dhcpv4(self):
        conf_file = dhclient_conf_dir + self._ifname + '.conf'
        pidfile = dhclient_conf_dir + self._ifname + '.pid'
        leasefile = dhclient_conf_dir + self._ifname + '.leases'

        a = [
            '# generated by interface_config.py',
              'option rfc3442-classless-static-routes code 121 = array of unsigned integer 8;',
              'interface \"' + self._ifname + '\" {',
              '\tsend host-name \"' + socket.gethostname() + '\";',
              '\trequest subnet-mask, broadcast-address, routers, domain-name-servers, rfc3442-classless-static-routes, domain-name, interface-mtu;',
              '}'
        ]

        cnf = ""
        for ln in a:
            cnf += str(ln + "\n")
        open(conf_file, 'w').write(cnf)
        if os.path.exists(dhclient_conf_dir + self._ifname + '.pid'):
            try:
                ret = subprocess.check_output(
                    ['/sbin/dhclient -4 -r -pf ' + pidfile], shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
        try:
            ret = subprocess.check_output(
                ['/sbin/dhclient -4 -q -nw -cf ' + conf_file + ' -pf ' + pidfile + ' -lf ' + leasefile + ' ' + self._ifname], shell=True).decode()
            return True
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def del_dhcpv4(self):
        conf_file = dhclient_conf_dir + self._ifname + '.conf'
        pidfile = dhclient_conf_dir + self._ifname + '.pid'
        leasefile = dhclient_conf_dir + self._ifname + '.leases'
        if not os.path.exists(pidfile):
            return 1
        try:
            ret = subprocess.check_output(
                ['/sbin/dhclient -4 -r -pf ' + pidfile], shell=True).decode()
            return True
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def get_dhcpv4(self):
        pidfile = dhclient_conf_dir + self._ifname + '.pid'
        if not os.path.exists(pidfile):
            print (
                "no dhcp client running on interface {0}".format(self._ifname))
            return False
        else:
            pid = open(pidfile, 'r').read()
            print(
                "dhclient running on {0} with pid {1}".format(self._ifname, pid))
            return True

    def set_dhcpv6(self):
        conf_file = dhclient_conf_dir + self._ifname + '.v6conf'
        pidfile = dhclient_conf_dir + self._ifname + '.v6pid'
        leasefile = dhclient_conf_dir + self._ifname + '.v6leases'
        a = [
            '# generated by interface_config.py',
              'interface \"' + self._ifname + '\" {',
              '\trequest routers, domain-name-servers, domain-name;',
              '}'
        ]
        cnf = ""
        for ln in a:
            cnf += str(ln + "\n")
        open(conf_file, 'w').write(cnf)
        subprocess.call(
            ['sysctl', '-q', '-w', 'net.ipv6.conf.' + self._ifname + '.accept_ra=0'])
        if os.path.exists(pidfile):
            try:
                ret = subprocess.check_output(
                    ['/sbin/dhclient -6 -q -x -pf ' + pidfile], shell=True).decode()
            except subprocess.CalledProcessError as e:
                if self._debug():
                    self._debug(e)
        try:
            ret = subprocess.check_output(
                ['/sbin/dhclient -6 -q -nw -cf ' + conf_file + ' -pf ' + pidfile + ' -lf ' + leasefile + ' ' + self._ifname], shell=True).decode()
            return True
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def del_dhcpv6(self):
        conf_file = dhclient_conf_dir + self._ifname + '.v6conf'
        pidfile = dhclient_conf_dir + self._ifname + '.v6pid'
        leasefile = dhclient_conf_dir + self._ifname + '.v6leases'
        if not os.path.exists(pidfile):
            return 1
        try:
            ret = subprocess.check_output(
                ['/sbin/dhclient -6 -q -x -pf ' + pidfile], shell=True).decode()
            subprocess.call(
                ['sysctl', '-q', '-w', 'net.ipv6.conf.' + self._ifname + '.accept_ra=1'])
            return True
        except subprocess.CalledProcessError as e:
            if self._debug():
                self._debug(e)
            return None

    def get_dhcpv6(self):
        pidfile = dhclient_conf_dir + self._ifname + '.v6pid'
        if not os.path.exists(pidfile):
            print (
                "no dhcpv6 client running on interface {0}".format(self._ifname))
            return False
        else:
            pid = open(pidfile, 'r').read()
            print(
                "dhclientv6 running on {0} with pid {1}".format(self._ifname, pid))
            return True


# TODO: dhcpv6-pd via dhclient
