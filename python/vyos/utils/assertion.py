# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

def assert_boolean(b):
    if int(b) not in (0, 1):
        raise ValueError(f'Value {b} out of range')

def assert_range(value, lower=0, count=3):
    if int(value, 16) not in range(lower, lower+count):
        raise ValueError("Value out of range")

def assert_list(s, l):
    if s not in l:
        o = ' or '.join([f'"{n}"' for n in l])
        raise ValueError(f'state must be {o}, got {s}')

def assert_number(n):
    if not str(n).isnumeric():
        raise ValueError(f'{n} must be a number')

def assert_positive(n, smaller=0):
    assert_number(n)
    if int(n) < smaller:
        raise ValueError(f'{n} is smaller than {smaller}')

def assert_mtu(mtu, ifname):
    assert_number(mtu)

    import json
    from vyos.utils.process import cmd
    out = cmd(f'ip -j -d link show dev {ifname}')
    # [{"ifindex":2,"ifname":"eth0","flags":["BROADCAST","MULTICAST","UP","LOWER_UP"],"mtu":1500,"qdisc":"pfifo_fast","operstate":"UP","linkmode":"DEFAULT","group":"default","txqlen":1000,"link_type":"ether","address":"08:00:27:d9:5b:04","broadcast":"ff:ff:ff:ff:ff:ff","promiscuity":0,"min_mtu":46,"max_mtu":16110,"inet6_addr_gen_mode":"none","num_tx_queues":1,"num_rx_queues":1,"gso_max_size":65536,"gso_max_segs":65535}]
    parsed = json.loads(out)[0]
    min_mtu = int(parsed.get('min_mtu', '0'))
    # cur_mtu = parsed.get('mtu',0),
    max_mtu = int(parsed.get('max_mtu', '0'))
    cur_mtu = int(mtu)

    if (min_mtu and cur_mtu < min_mtu) or cur_mtu < 68:
        raise ValueError(f'MTU is too small for interface "{ifname}": {mtu} < {min_mtu}')
    if (max_mtu and cur_mtu > max_mtu) or cur_mtu > 65536:
        raise ValueError(f'MTU is too small for interface "{ifname}": {mtu} > {max_mtu}')

def assert_mac(m, test_all_zero=True):
    split = m.split(':')
    size = len(split)

    # a mac address consits out of 6 octets
    if size != 6:
        raise ValueError(f'wrong number of MAC octets ({size}): {m}')

    octets = []
    try:
        for octet in split:
            octets.append(int(octet, 16))
    except ValueError:
        raise ValueError(f'invalid hex number "{octet}" in : {m}')

    # validate against the first mac address byte if it's a multicast
    # address
    if octets[0] & 1:
        raise ValueError(f'{m} is a multicast MAC address')

    # overall mac address is not allowed to be 00:00:00:00:00:00
    if test_all_zero and sum(octets) == 0:
        raise ValueError('00:00:00:00:00:00 is not a valid MAC address')

    if octets[:5] == (0, 0, 94, 0, 1):
        raise ValueError(f'{m} is a VRRP MAC address')
