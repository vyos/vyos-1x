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
import subprocess
from copy import deepcopy
from netifaces import interfaces

from vyos import ConfigError
from vyos.config import Config
from vyos.configdict import list_diff
from vyos.ifconfig import WireGuardIf

kdir = r'/config/auth/wireguard'


def _check_kmod():
    if not os.path.exists('/sys/module/wireguard'):
        if os.system('sudo modprobe wireguard') != 0:
            raise ConfigError("modprobe wireguard failed")


def _migrate_default_keys():
    if os.path.exists('{}/private.key'.format(kdir)) and not os.path.exists('{}/default/private.key'.format(kdir)):
        old_umask = os.umask(0o027)
        location = '{}/default'.format(kdir)
        subprocess.call(['sudo mkdir -p ' + location], shell=True)
        subprocess.call(['sudo chgrp vyattacfg ' + location], shell=True)
        subprocess.call(['sudo chmod 750 ' + location], shell=True)
        os.rename('{}/private.key'.format(kdir),
                  '{}/private.key'.format(location))
        os.rename('{}/public.key'.format(kdir),
                  '{}/public.key'.format(location))
        os.umask(old_umask)


def get_config():
    c = Config()
    if not c.exists(['interfaces', 'wireguard']):
        return None

    dflt_cnf = {
        'intfc': '',
        'addr': [],
        'addr_remove': [],
        'descr': '',
        'lport': None,
        'delete': False,
        'state': 'up',
        'fwmark': 0x00,
        'mtu': 1420,
        'peer': {},
        'peer_remove': [],
        'pk': '{}/default/private.key'.format(kdir)
    }

    if os.getenv('VYOS_TAGNODE_VALUE'):
        ifname = str(os.environ['VYOS_TAGNODE_VALUE'])
        wg = deepcopy(dflt_cnf)
        wg['intfc'] = ifname
        wg['descr'] = ifname
    else:
        print("ERROR: VYOS_TAGNODE_VALUE undefined")
        sys.exit(1)

    c.set_level(['interfaces', 'wireguard'])

    # interface removal state
    if not c.exists(ifname) and c.exists_effective(ifname):
        wg['delete'] = True

    if not wg['delete']:
        c.set_level(['interfaces', 'wireguard', ifname])
        if c.exists(['address']):
            wg['addr'] = c.return_values(['address'])

        # determine addresses which need to be removed
        eff_addr = c.return_effective_values(['address'])
        wg['addr_remove'] = list_diff(eff_addr, wg['addr'])

        # ifalias description
        if c.exists(['description']):
            wg['descr'] = c.return_value(['description'])

        # link state
        if c.exists(['disable']):
            wg['state'] = 'down'

        # local port to listen on
        if c.exists(['port']):
            wg['lport'] = c.return_value(['port'])

        # fwmark value
        if c.exists(['fwmark']):
            wg['fwmark'] = c.return_value(['fwmark'])

        # mtu
        if c.exists('mtu'):
            wg['mtu'] = c.return_value('mtu')

        # private key
        if c.exists(['private-key']):
            wg['pk'] = "{0}/{1}/private.key".format(
                kdir, c.return_value(['private-key']))

        # peer removal, wg identifies peers by its pubkey
        peer_eff = c.list_effective_nodes(['peer'])
        peer_rem = list_diff(peer_eff, c.list_nodes(['peer']))
        for p in peer_rem:
            wg['peer_remove'].append(
                c.return_effective_value(['peer', p, 'pubkey']))

        # peer settings
        if c.exists(['peer']):
            for p in c.list_nodes(['peer']):
                if not c.exists(['peer', p, 'disable']):
                    wg['peer'].update(
                        {
                            p: {
                                'allowed-ips': [],
                              'endpoint': '',
                              'pubkey': ''
                            }
                        }
                    )
                    # peer allowed-ips
                    if c.exists(['peer', p, 'allowed-ips']):
                        wg['peer'][p]['allowed-ips'] = c.return_values(
                            ['peer', p, 'allowed-ips'])
                    # peer endpoint
                    if c.exists(['peer', p, 'endpoint']):
                        wg['peer'][p]['endpoint'] = c.return_value(
                            ['peer', p, 'endpoint'])
                    # persistent-keepalive
                    if c.exists(['peer', p, 'persistent-keepalive']):
                        wg['peer'][p]['persistent-keepalive'] = c.return_value(
                            ['peer', p, 'persistent-keepalive'])
                    # preshared-key
                    if c.exists(['peer', p, 'preshared-key']):
                        wg['peer'][p]['psk'] = c.return_value(
                            ['peer', p, 'preshared-key'])
                    # peer pubkeys
                    key_eff = c.return_effective_value(['peer', p, 'pubkey'])
                    key_cfg = c.return_value(['peer', p, 'pubkey'])
                    wg['peer'][p]['pubkey'] = key_cfg

                    # on a pubkey change we need to remove the pubkey first
                    # peers are identified by pubkey, so key update means
                    # peer removal and re-add
                    if key_eff != key_cfg and key_eff != None:
                        wg['peer_remove'].append(key_cfg)

                # if a peer is disabled, we have to exec a remove for it's pubkey
                else:
                  peer_key = c.return_value(['peer', p, 'pubkey'])
                  wg['peer_remove'].append(peer_key)
    return wg


def verify(c):
    if not c:
        return None

    if not os.path.exists(c['pk']):
        raise ConfigError(
            "No keys found, generate them by executing: \'run generate wireguard [keypair|named-keypairs]\'")

    if not c['delete']:
        if not c['addr']:
            raise ConfigError("ERROR: IP address required")
        if not c['peer']:
            raise ConfigError("ERROR: peer required")
        for p in c['peer']:
            if not c['peer'][p]['allowed-ips']:
                raise ConfigError("ERROR: allowed-ips required for peer " + p)
            if not c['peer'][p]['pubkey']:
                raise ConfigError("peer pubkey required for peer " + p)


def apply(c):
    # no wg configs left, remove all interface from system
    # maybe move it into ifconfig.py
    if not c:
        net_devs = os.listdir('/sys/class/net/')
        for dev in net_devs:
            if os.path.isdir('/sys/class/net/' + dev):
                buf = open('/sys/class/net/' + dev + '/uevent', 'r').read()
                if re.search("DEVTYPE=wireguard", buf, re.I | re.M):
                    wg_intf = re.sub("INTERFACE=", "", re.search(
                        "INTERFACE=.*", buf, re.I | re.M).group(0))
                    subprocess.call(
                        ['ip l d dev ' + wg_intf + ' >/dev/null'], shell=True)
        return None

    # init wg class
    intfc = WireGuardIf(c['intfc'])

    # single interface removal
    if c['delete']:
        intfc.remove()
        return None

    # remove IP addresses
    for ip in c['addr_remove']:
        intfc.del_addr(ip)

    # add IP addresses
    for ip in c['addr']:
        intfc.add_addr(ip)

    # interface mtu
    intfc.set_mtu(int(c['mtu']))

    # ifalias for snmp from description
    intfc.set_alias(str(c['descr']))

    # remove peers
    if c['peer_remove']:
        for pkey in c['peer_remove']:
            intfc.remove_peer(pkey)

    # peer pubkey
    # setting up the wg interface
    intfc.config['private-key'] = c['pk']
    for p in c['peer']:
        # peer pubkey
        intfc.config['pubkey'] = str(c['peer'][p]['pubkey'])
        # peer allowed-ips
        intfc.config['allowed-ips'] = c['peer'][p]['allowed-ips']
        # local listen port
        if c['lport']:
            intfc.config['port'] = c['lport']
        # fwmark
        if c['fwmark']:
            intfc.config['fwmark'] = c['fwmark']
        # endpoint
        if c['peer'][p]['endpoint']:
            intfc.config['endpoint'] = c['peer'][p]['endpoint']

        # persistent-keepalive
        if 'persistent-keepalive' in c['peer'][p]:
            intfc.config['keepalive'] = c['peer'][p]['persistent-keepalive']

        # maybe move it into ifconfig.py
        # preshared-key - needs to be read from a file
        if 'psk' in c['peer'][p]:
            psk_file = '/config/auth/wireguard/psk'
            old_umask = os.umask(0o077)
            open(psk_file, 'w').write(str(c['peer'][p]['psk']))
            os.umask(old_umask)
            intfc.config['psk'] = psk_file
        intfc.update()

    # interface state
    intfc.set_state(c['state'])

    return None

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
