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
    if not ifname:
      raise Exception("interface name required")
    if not os.path.exists('/sys/class/net/{0}'.format(ifname)) and not type:
      raise Exception("interface {0} not found".format(str(ifname)))
    else:
      if not os.path.exists('/sys/class/net/{0}'.format(ifname)):
        try:
          ret = subprocess.check_output(['ip link add dev ' + str(ifname) + ' type ' + type], stderr=subprocess.STDOUT, shell=True).decode()
        except subprocess.CalledProcessError as e:
          if self._debug():
            self._debug(e)
          if "Operation not supported" in str(e.output.decode()):
            print(str(e.output.decode()))
            sys.exit(0)

    self._ifname = str(ifname)


  @property
  def mtu(self):
    try:
      ret = subprocess.check_output(['ip -j link list dev ' + self._ifname], shell=True).decode()
      a = json.loads(ret)[0]
      return a['mtu']
    except subprocess.CalledProcessError as e:
        if self._debug():
          self._debug(e)
        return None

  @mtu.setter
  def mtu(self, mtu=None):
    if mtu < 68 or mtu > 9000:
      raise ValueError("mtu size invalid value")
    self._mtu = mtu
    try:
      ret = subprocess.check_output(['ip link set mtu ' + str(mtu) + ' dev ' + self._ifname], shell=True).decode()
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)


  @property
  def macaddr(self):
    try:
      ret = subprocess.check_output(['ip -j -4 link show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
      j = json.loads(ret)
      return j[0]['address']
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  @macaddr.setter
  def macaddr(self, mac=None):
    if not re.search('^[a-f0-9:]{17}$', str(mac)):
      raise ValueError("mac address invalid")
    self._macaddr = str(mac)
    try:
      ret = subprocess.check_output(['ip link set address ' + mac + ' ' + self._ifname], shell=True).decode()
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)


  @property
  def ifalias(self):
    return open('/sys/class/net/{0}/ifalias'.format(self._ifname),'r').read()

  @ifalias.setter
  def ifalias(self, ifalias=None):
    if not ifalias:
      self._ifalias = self._ifname
    else:
      self._ifalias = str(ifalias)
    open('/sys/class/net/{0}/ifalias'.format(self._ifname),'w').write(self._ifalias)


  @property
  def linkstate(self):
    try:
      ret = subprocess.check_output(['ip -j link show ' + self._ifname], shell=True).decode()
      s = json.loads(ret)
      return s[0]['operstate'].lower()
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  @linkstate.setter
  def linkstate(self, state='up'):
    if str(state).lower() == 'up' or str(state).lower() == 'down':
      self._linkstate = str(state).lower()
    else:
      self._linkstate = 'up'
    try:
      ret = subprocess.check_output(['ip link set dev ' + self._ifname + ' ' + state], shell=True).decode()
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)



  def _debug(self, e=None):
    """
        export DEBUG=1 to see debug messages
    """
    if os.getenv('DEBUG') == '1':
      if e:
        print ("Exception raised:\ncommand: {0}\nerror code: {1}\nsubprocess output: {2}".format(e.cmd, e.returncode, e.output.decode()) )
      return True
    return False

  def get_mtu(self):
    print ("function get_mtu() is depricated and will be removed soon")
    try:
      ret = subprocess.check_output(['ip -j link list dev ' + self._ifname], shell=True).decode()
      a = json.loads(ret)[0]
      return a['mtu']
    except subprocess.CalledProcessError as e:
        if self._debug():
          self._debug(e)
        return None


  def get_macaddr(self):
    print ("function get_macaddr() is depricated and will be removed soon")
    try:
      ret = subprocess.check_output(['ip -j -4 link show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
      j = json.loads(ret)
      return j[0]['address']
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def get_alias(self):
    print ("function get_alias() is depricated and will be removed soon")
    return open('/sys/class/net/{0}/ifalias'.format(self._ifname),'r').read()

  def del_alias(self):
    open('/sys/class/net/{0}/ifalias'.format(self._ifname),'w').write()

  def get_link_state(self):
    print ("function get_link_state() is depricated and will be removed soon")
    try:
      ret = subprocess.check_output(['ip -j link show ' + self._ifname], shell=True).decode()
      s = json.loads(ret)
      return s[0]['operstate'].lower()
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def remove_interface(self):
    try:
      ret = subprocess.check_output(['ip link del dev ' + self._ifname], shell=True).decode()
      return 0
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def get_addr(self, ret_prefix=None):
    """
        universal: reads all IPs assigned to an interface and returns it in a list,
        or None if no IP address is assigned to the interface. Also may return
        in prefix format if set ret_prefix
    """
    ips = []
    try:
      ret = subprocess.check_output(['ip -j addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
      j = json.loads(ret)
      for i in j:
        if len(i) != 0:
          for addr in i['addr_info']:
            if ret_prefix:
              ips.append(addr['local'] + "/" + str(addr['prefixlen']))
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
      ret = subprocess.check_output(['ip -j -4 addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
      ret = subprocess.check_output(['ip -j -6 addr show dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip ' + proto + ' address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip ' + proto + ' address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip -4 address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip -4 address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip -6 address add ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
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
        ret = subprocess.check_output(['ip -6 address del ' + ip + ' dev ' + self._ifname], stderr=subprocess.STDOUT, shell=True).decode()
      except subprocess.CalledProcessError as e:
        if self._debug():
          self._debug(e)
        return None
    return True


  #### replace dhcpv4/v6 with systemd.networkd?
  def set_dhcpv4(self):
    conf_file = dhclient_conf_dir + self._ifname + '.conf'
    pidfile   = dhclient_conf_dir + self._ifname + '.pid'
    leasefile = dhclient_conf_dir + self._ifname + '.leases'

    a = [
          '# generated by interface_config.py',
          'option rfc3442-classless-static-routes code 121 = array of unsigned integer 8;',
          'interface \"' + self._ifname + '\" {',
          '\tsend host-name \"' + socket.gethostname() +'\";',
          '\trequest subnet-mask, broadcast-address, routers, domain-name-servers, rfc3442-classless-static-routes, domain-name, interface-mtu;',
          '}'
        ]

    cnf = ""
    for ln in a:
      cnf +=str(ln + "\n")
    open(conf_file, 'w').write(cnf)
    if os.path.exists(dhclient_conf_dir + self._ifname + '.pid'):
      try:
        ret = subprocess.check_output(['/sbin/dhclient -4 -r -pf ' + pidfile], shell=True).decode()
      except subprocess.CalledProcessError as e:
        if self._debug():
          self._debug(e)
    try:
      ret = subprocess.check_output(['/sbin/dhclient -4 -q -nw -cf ' + conf_file + ' -pf ' + pidfile + ' -lf ' + leasefile + ' ' + self._ifname], shell=True).decode()
      return True
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def del_dhcpv4(self):
    conf_file = dhclient_conf_dir + self._ifname + '.conf'
    pidfile   = dhclient_conf_dir + self._ifname + '.pid'
    leasefile = dhclient_conf_dir + self._ifname + '.leases'
    if not os.path.exists(pidfile):
      return 1
    try:
      ret = subprocess.check_output(['/sbin/dhclient -4 -r -pf ' + pidfile], shell=True).decode()
      return True
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def get_dhcpv4(self):
    pidfile = dhclient_conf_dir + self._ifname + '.pid'
    if not os.path.exists(pidfile):
      print ("no dhcp client running on interface {0}".format(self._ifname))
      return False
    else:
      pid = open(pidfile, 'r').read()
      print("dhclient running on {0} with pid {1}".format(self._ifname, pid))
      return True


  def set_dhcpv6(self):
    conf_file = dhclient_conf_dir +  self._ifname + '.v6conf'
    pidfile   = dhclient_conf_dir + self._ifname + '.v6pid'
    leasefile = dhclient_conf_dir + self._ifname + '.v6leases'
    a = [
          '# generated by interface_config.py',
          'interface \"' + self._ifname + '\" {',
          '\trequest routers, domain-name-servers, domain-name;',
          '}'
        ]
    cnf = ""
    for ln in a:
      cnf +=str(ln + "\n")
    open(conf_file, 'w').write(cnf)
    subprocess.call(['sysctl', '-q', '-w', 'net.ipv6.conf.' + self._ifname + '.accept_ra=0'])
    if os.path.exists(pidfile):
      try:
        ret = subprocess.check_output(['/sbin/dhclient -6 -q -x -pf ' + pidfile], shell=True).decode()
      except subprocess.CalledProcessError as e:
        if self._debug():
          self._debug(e)
    try:
      ret = subprocess.check_output(['/sbin/dhclient -6 -q -nw -cf ' + conf_file + ' -pf ' + pidfile + ' -lf ' + leasefile + ' ' + self._ifname], shell=True).decode()
      return True
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def del_dhcpv6(self):
    conf_file = dhclient_conf_dir +  self._ifname + '.v6conf'
    pidfile   = dhclient_conf_dir + self._ifname + '.v6pid'
    leasefile = dhclient_conf_dir + self._ifname + '.v6leases'
    if not os.path.exists(pidfile):
      return 1
    try:
      ret = subprocess.check_output(['/sbin/dhclient -6 -q -x -pf ' + pidfile], shell=True).decode()
      subprocess.call(['sysctl', '-q', '-w', 'net.ipv6.conf.' + self._ifname + '.accept_ra=1'])
      return True
    except subprocess.CalledProcessError as e:
      if self._debug():
        self._debug(e)
      return None

  def get_dhcpv6(self):
    pidfile = dhclient_conf_dir + self._ifname + '.v6pid'
    if not os.path.exists(pidfile):
      print ("no dhcpv6 client running on interface {0}".format(self._ifname))
      return False
    else:
      pid = open(pidfile, 'r').read()
      print("dhclientv6 running on {0} with pid {1}".format(self._ifname, pid))
      return True


#### TODO: dhcpv6-pd via dhclient

