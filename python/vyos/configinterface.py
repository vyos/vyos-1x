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

def validate_mac_address(addr):
    # a mac address consits out of 6 octets
    octets = len(addr.split(':'))
    if octets != 6:
        raise ValueError('wrong number of MAC octets: {} '.format(octets))

    # validate against the first mac address byte if it's a multicast address
    if int(addr.split(':')[0]) & 1:
        raise ValueError('{} is a multicast MAC address'.format(addr))

    # overall mac address is not allowed to be 00:00:00:00:00:00
    if sum(int(i, 16) for i in addr.split(':')) == 0:
        raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

    # check for VRRP mac address
    if addr.split(':')[0] == '0' and addr.split(':')[1] == '0' and addr.split(':')[2] == '94' and addr.split(':')[3] == '0' and addr.split(':')[4] == '1':
        raise ValueError('{} is a VRRP MAC address')

    pass

def set_mac_address(intf, addr):
    """
    Configure interface mac address using iproute2 command
    """
    validate_mac_address(addr)

    os.system('ip link set {} address {}'.format(intf, addr))

def set_description(intf, desc):
    """
    Sets the interface secription reported usually by SNMP
    """
    with open('/sys/class/net/' + intf + '/ifalias', 'w') as f:
      f.write(desc)


def set_arp_cache_timeout(intf, tmoMS):
    """
    Configure the ARP cache entry timeout in milliseconds
    """
    with open('/proc/sys/net/ipv4/neigh/' + intf + '/base_reachable_time_ms', 'w') as f:
      f.write(tmoMS)

def set_multicast_querier(intf, enable):
    """
    Sets whether the bridge actively runs a multicast querier or not. When a
    bridge receives a 'multicast host membership' query from another network host,
    that host is tracked based on the time that the query was received plus the
    multicast query interval time.

    use enable=1 to enable or enable=0 to disable
    """

    if int(enable) >= 0 and int(enable) <= 1:
      with open('/sys/devices/virtual/net/' + intf + '/bridge/multicast_querier', 'w') as f:
        f.write(str(enable))
    else:
      raise ValueError("malformed configuration string on interface {}: enable={}".format(intf, enable))

def set_link_detect(intf, enable):
    """
    0 - Allow packets to be received for the address on this interface
    even if interface is disabled or no carrier.

    1 - Ignore packets received if interface associated with the incoming
    address is down.

    2 - Ignore packets received if interface associated with the incoming
    address is down or has no carrier.

    Kernel Source: Documentation/networking/ip-sysctl.txt
    """

    # Note can't use sysctl it is broken for vif name because of dots
    # link_filter values:
    #   0 - always receive
    #   1 - ignore receive if admin_down
    #   2 - ignore receive if admin_down or link down

    with open('/proc/sys/net/ipv4/conf/' + intf + '/link_filter', 'w') as f:
      if enable == True or enable == 1:
        f.write('2')
        if os.path.isfile('/usr/bin/vtysh'):
          os.system('/usr/bin/vtysh -c "configure terminal" -c "interface {}" -c "link-detect"'.format(intf))
      else:
        f.write('1')
        if os.path.isfile('/usr/bin/vtysh'):
          os.system('/usr/bin/vtysh -c "configure terminal" -c "interface {}" -c "no link-detect"'.format(intf))
