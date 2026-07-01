#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import os
import argparse

from psutil import process_iter
from time import sleep

from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import call
from vyos.utils.commit import commit_in_progress

def check_ppp_interface(interface):
    if not os.path.isfile(f'/etc/ppp/peers/{interface}'):
        print(f'Interface {interface} does not exist!')
        exit(1)

def check_ppp_running(interface):
    """ Check if PPP process is running in the interface in question """
    for p in process_iter():
        if "pppd" in p.name():
            if interface in p.cmdline():
                return True

    return False

def _wwan_ifnum(interface):
    """Extract numeric index from 'wwanN'."""
    return int(interface.replace('wwan', ''))

def _wwan_client():
    """Return a synchronous WWAN FSM D-Bus client."""
    from vyos.utils.wwan.wwan_client import WWANClientSync
    return WWANClientSync()

def connect(interface):
    """ Connect dialer interface """

    if interface.startswith('pppoe') or interface.startswith('sstpc'):
        check_ppp_interface(interface)
        # Check if interface is already dialed
        if os.path.isdir(f'/sys/class/net/{interface}'):
            print(f'Interface {interface}: already connected!')
        elif check_ppp_running(interface):
            print(f'Interface {interface}: connection is being established!')
        else:
            print(f'Interface {interface}: connecting...')
            call(f'systemctl restart ppp@{interface}.service')
    elif interface.startswith('wwan'):
        # Route through the FSM so it clears the user-disconnect inhibit
        # and drives the modem through its own state machine.
        try:
            client = _wwan_client()
            ifnum = _wwan_ifnum(interface)
            # In always-on mode the bearer is FSM-managed (auto-connect at
            # boot, self-heal on failure), so a manual connect is rejected.
            # Check the mode BEFORE the bearer-status short-circuit so the
            # rejection surfaces regardless of the current bearer state
            # (otherwise an already-connected always-on modem would print a
            # misleading "already connected!" instead of the rejection).
            mode = client.get_status(ifnum).get('connection_mode', 'always-on')
            if mode == 'always-on':
                # Call through so the service's clear InvalidConnectionMode
                # error is what the operator sees.
                client.connect(ifnum)
            elif client.get_bearer_status(ifnum) == 'connected':
                print(f'Interface {interface}: already connected!')
            else:
                print(f'Interface {interface}: connecting...')
                client.connect(ifnum)
        except Exception as exc:
            print(f'Interface {interface}: connect failed: {exc}')
            exit(1)
    else:
        print(f'Unknown interface {interface}, cannot connect. Aborting!')

    # Reaply QoS configuration
    config = ConfigTreeQuery()
    if config.exists(f'qos interface {interface}'):
        count = 1
        while commit_in_progress():
            if ( count % 60 == 0 ):
                print(f'Commit still in progress after {count}s - waiting')
            count += 1
            sleep(1)
        call('/usr/libexec/vyos/conf_mode/qos.py')

def disconnect(interface):
    """ Disconnect dialer interface """

    if interface.startswith('pppoe') or interface.startswith('sstpc'):
        check_ppp_interface(interface)

        # Check if interface is already down
        if not check_ppp_running(interface):
            print(f'Interface {interface}: connection is already down')
        else:
            print(f'Interface {interface}: disconnecting...')
            call(f'systemctl stop ppp@{interface}.service')
    elif interface.startswith('wwan'):
        # Route through the FSM — it sets the user-disconnect inhibit so
        # the bearer does not automatically reconnect.
        try:
            client = _wwan_client()
            ifnum = _wwan_ifnum(interface)
            # In always-on mode the bearer is FSM-managed and self-healing,
            # so a manual disconnect is rejected.  Check the mode BEFORE the
            # bearer-status short-circuit so the rejection surfaces
            # regardless of the current bearer state (otherwise a
            # disconnected always-on modem would print a misleading
            # "connection is already down" instead of the rejection).
            mode = client.get_status(ifnum).get('connection_mode', 'always-on')
            if mode == 'always-on':
                # Call through so the service's clear InvalidConnectionMode
                # error is what the operator sees.
                client.disconnect(ifnum)
            elif client.get_bearer_status(ifnum) != 'connected':
                print(f'Interface {interface}: connection is already down')
            else:
                print(f'Interface {interface}: disconnecting...')
                client.disconnect(ifnum)
        except Exception as exc:
            print(f'Interface {interface}: disconnect failed: {exc}')
            exit(1)
    else:
        print(f'Unknown interface {interface}, cannot disconnect. Aborting!')

def main():
    parser = argparse.ArgumentParser()
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--connect", help="Bring up a connection-oriented network interface", action="store_true")
    group.add_argument("--disconnect", help="Take down connection-oriented network interface", action="store_true")
    group.add_argument("--reconnect", help="Reconnect connection-oriented network interface", action="store_true")
    parser.add_argument("--interface", help="Interface name", action="store", required=True)
    args = parser.parse_args()

    # Disallow connecting interfaces while their configuration might be changing
    if args.connect or args.reconnect:
        if commit_in_progress():
            print('Cannot connect while a commit is in progress')
            exit(1)

    if args.connect:
        connect(args.interface)
    elif args.disconnect:
        disconnect(args.interface)
    elif args.reconnect:
        disconnect(args.interface)
        connect(args.interface)
    else:
        parser.print_help()

    exit(0)

if __name__ == '__main__':
     main()
