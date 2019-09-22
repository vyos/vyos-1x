#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys
import os
import re
import syslog as sl
import subprocess

from vyos.config import Config
from vyos import ConfigError
from vyos.ifconfig import WireGuardIf

try:
    ifname = str(os.environ['VYOS_TAGNODE_VALUE'])
    intfc = WireGuardIf(ifname)
except KeyError:
    print("Interface not specified")
    sys.exit(1)

kdir = r'/config/auth/wireguard'

def _check_kmod():
    if not os.path.exists('/sys/module/wireguard'):
        sl.syslog(sl.LOG_NOTICE, "loading wirguard kmod")
        if os.system('sudo modprobe wireguard') != 0:
            sl.syslog(sl.LOG_NOTICE, "modprobe wireguard failed")
            raise ConfigError("modprobe wireguard failed")


def _migrate_default_keys():
    if os.path.exists('{}/private.key'.format(kdir)) and not os.path.exists('{}/default/private.key'.format(kdir)):
        sl.syslog(sl.LOG_NOTICE, "migrate keypair to default")
        old_umask = os.umask(0o027)
        location = '{}/default'.format(kdir)
        subprocess.call(['sudo mkdir -p ' + location], shell=True)
        subprocess.call(['sudo chgrp vyattacfg ' + location], shell=True)
        subprocess.call(['sudo chmod 750 ' + location], shell=True)
        os.rename('{}/private.key'.format(kdir),'{}/private.key'.format(location))
        os.rename('{}/public.key'.format(kdir),'{}/public.key'.format(location))
        os.umask(old_umask)


def get_config():
    c = Config()
    if not c.exists('interfaces wireguard'):
        return None

    config_data = {
        ifname: {
            'addr': '',
            'descr': ifname,
            'lport': None,
            'status': 'exists',
            'state': 'enabled',
            'fwmark': 0x00,
            'mtu': 1420,
            'peer': {},
            'pk'  : '{}/default/private.key'.format(kdir)
        }
    }

    c.set_level('interfaces wireguard')
    if not c.exists_effective(ifname):
        config_data[ifname]['status'] = 'create'

    if not c.exists(ifname) and c.exists_effective(ifname):
        config_data[ifname]['status'] = 'delete'

    if config_data[ifname]['status'] != 'delete':
        if c.exists(ifname + ' address'):
            config_data[ifname]['addr'] = c.return_values(ifname + ' address')
        if c.exists(ifname + ' disable'):
            config_data[ifname]['state'] = 'disable'
        if c.exists(ifname + ' port'):
            config_data[ifname]['lport'] = c.return_value(ifname + ' port')
        if c.exists(ifname + ' fwmark'):
            config_data[ifname]['fwmark'] = c.return_value(ifname + ' fwmark')
        if c.exists(ifname + ' description'):
            config_data[ifname]['descr'] = c.return_value(
                ifname + ' description')
        if c.exists(ifname + ' mtu'):
            config_data[ifname]['mtu'] = c.return_value(ifname + ' mtu')
        if c.exists(ifname + ' private-key'):
            config_data[ifname]['pk'] = "{0}/{1}/private.key".format(kdir,c.return_value(ifname + ' private-key')) 
        if c.exists(ifname + ' peer'):
            for p in c.list_nodes(ifname + ' peer'):
                if not c.exists(ifname + ' peer ' + p + ' disable'):
                    config_data[ifname]['peer'].update(
                        {
                            p: {
                                'allowed-ips': [],
                              'endpoint': '',
                              'pubkey': ''
                            }
                        }
                    )
                    if c.exists(ifname + ' peer ' + p + ' pubkey'):
                        config_data[ifname]['peer'][p]['pubkey'] = c.return_value(
                            ifname + ' peer ' + p + ' pubkey')
                    if c.exists(ifname + ' peer ' + p + ' allowed-ips'):
                        config_data[ifname]['peer'][p]['allowed-ips'] = c.return_values(
                            ifname + ' peer ' + p + ' allowed-ips')
                    if c.exists(ifname + ' peer ' + p + ' endpoint'):
                        config_data[ifname]['peer'][p]['endpoint'] = c.return_value(
                            ifname + ' peer ' + p + ' endpoint')
                    if c.exists(ifname + ' peer ' + p + ' persistent-keepalive'):
                        config_data[ifname]['peer'][p]['persistent-keepalive'] = c.return_value(
                            ifname + ' peer ' + p + ' persistent-keepalive')
                    if c.exists(ifname + ' peer ' + p + ' preshared-key'):
                        config_data[ifname]['peer'][p]['psk'] = c.return_value(
                            ifname + ' peer ' + p + ' preshared-key')

    return config_data

def verify(c):
    if not c:
        return None

    if not os.path.exists(c[ifname]['pk']):
        raise ConfigError(
            "No keys found, generate them by executing: \'run generate wireguard [keypair|named-keypairs]\'")

    if c[ifname]['status'] != 'delete':
        if not c[ifname]['addr']:
            raise ConfigError("ERROR: IP address required")
        if not c[ifname]['peer']:
            raise ConfigError("ERROR: peer required")
        for p in c[ifname]['peer']:
            if not c[ifname]['peer'][p]['allowed-ips']:
                raise ConfigError("ERROR: allowed-ips required for peer " + p)
            if not c[ifname]['peer'][p]['pubkey']:
                raise ConfigError("peer pubkey required for peer " + p)


def apply(c):
    # no wg config left, delete all wireguard devices, if any
    if not c:
        net_devs = os.listdir('/sys/class/net/')
        for dev in net_devs:
            if os.path.isdir('/sys/class/net/' + dev):
                buf = open('/sys/class/net/' + dev + '/uevent', 'r').read()
                if re.search("DEVTYPE=wireguard", buf, re.I | re.M):
                    wg_intf = re.sub("INTERFACE=", "", re.search(
                        "INTERFACE=.*", buf, re.I | re.M).group(0))
                    sl.syslog(sl.LOG_NOTICE, "removing interface " + wg_intf)
                    subprocess.call(
                        ['ip l d dev ' + wg_intf + ' >/dev/null'], shell=True)
        return None

    # interface removal
    if c[ifname]['status'] == 'delete':
        sl.syslog(sl.LOG_NOTICE, "removing interface " + ifname)
        intfc.remove()
        return None

    c_eff = Config()
    c_eff.set_level('interfaces wireguard')

    # interface state
    if c[ifname]['state'] == 'disable':
        sl.syslog(sl.LOG_NOTICE, "disable interface " + ifname)
        intfc.state = 'down'
    else:
        if not intfc.state == 'up':
            sl.syslog(sl.LOG_NOTICE, "enable interface " + ifname)
            intfc.state = 'up'

    # IP address
    if not c_eff.exists_effective(ifname + ' address'):
        for ip in c[ifname]['addr']:
            intfc.add_addr(ip)
    else:
        addr_eff = c_eff.return_effective_values(ifname + ' address')
        addr_rem = list(set(addr_eff) - set(c[ifname]['addr']))
        addr_add = list(set(c[ifname]['addr']) - set(addr_eff))

        if len(addr_rem) != 0:
            for ip in addr_rem:
                sl.syslog(
                    sl.LOG_NOTICE, "remove IP address {0} from {1}".format(ip, ifname))
                intfc.del_addr(ip)

        if len(addr_add) != 0:
            for ip in addr_add:
                sl.syslog(
                    sl.LOG_NOTICE, "add IP address {0} to {1}".format(ip, ifname))
                intfc.add_addr(ip)

    # interface MTU
    if c[ifname]['mtu'] != 1420:
        intfc.mtu = int(c[ifname]['mtu'])
    else:
    # default is set to 1420 in config_data
        intfc.mtu = int(c[ifname]['mtu'])

    # ifalias for snmp from description
    descr_eff = c_eff.return_effective_value(ifname + ' description')
    if descr_eff != c[ifname]['descr']:
        intfc.ifalias = str(c[ifname]['descr'])

    # peer deletion
    peer_eff = c_eff.list_effective_nodes(ifname + ' peer')
    peer_cnf = []

    try:
        for p in c[ifname]['peer']:
            peer_cnf.append(p)
    except KeyError:
        pass

    peer_rem = list(set(peer_eff) - set(peer_cnf))
    for p in peer_rem:
        pkey = c_eff.return_effective_value(ifname + ' peer ' + p + ' pubkey')
        intfc.remove_peer(pkey)

    # peer key update
    for p in peer_eff:
        if p in peer_cnf:
            ekey = c_eff.return_effective_value(
                ifname + ' peer ' + p + ' pubkey')
            nkey = c[ifname]['peer'][p]['pubkey']
            if nkey != ekey:
                sl.syslog(
                    sl.LOG_NOTICE, "peer {0} pubkey changed from {1} to {2} on interface {3}".format(p, ekey, nkey, ifname))
                intfc.remove_peer(ekey)

    intfc.config['private-key'] = c[ifname]['pk']
    for p in c[ifname]['peer']:
        intfc.config['pubkey'] = str(c[ifname]['peer'][p]['pubkey'])
        intfc.config['allowed-ips'] = (c[ifname]['peer'][p]['allowed-ips'])

        # listen-port
        if c[ifname]['lport']:
            intfc.config['port'] = c[ifname]['lport']

        # fwmark
        if c[ifname]['fwmark']:
            intfc.config['fwmark'] = c[ifname]['fwmark']

        # endpoint
        if c[ifname]['peer'][p]['endpoint']:
            intfc.config['endpoint'] = c[ifname]['peer'][p]['endpoint']

        # persistent-keepalive
        if 'persistent-keepalive' in c[ifname]['peer'][p]:
            intfc.config['keepalive'] = c[ifname][
                'peer'][p]['persistent-keepalive']

        # preshared-key - needs to be read from a file
        if 'psk' in c[ifname]['peer'][p]:
            psk_file = '/config/auth/wireguard/psk'
            old_umask = os.umask(0o077)
            open(psk_file, 'w').write(str(c[ifname]['peer'][p]['psk']))
            os.umask(old_umask)
            intfc.config['psk'] = psk_file

        intfc.update()

if __name__ == '__main__':
    try:
        _check_kmod()
        _migrate_default_keys()
        c = get_config()
        verify(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
