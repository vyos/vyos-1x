# Copyright (C) VyOS Inc.
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

"""ModemManager helpers shared between the WWAN conf_mode script and
vyos-netlinkd.

Both dial the very same modem with the very same parameters - conf_mode when
the CLI config is applied, vyos-netlinkd when a session has to be re-
established after it was lost. Keeping the option string and the mmcli
invocations in one place means a re-dial can never drift from what conf_mode
would have done.
"""

import os

from time import sleep

from vyos.utils.dict import dict_search
from vyos.utils.process import call
from vyos.utils.process import cmdl
from vyos.utils.process import DEVNULL
from vyos.utils.process import is_systemd_service_active

service_name = 'ModemManager.service'

# Bounded wait for a modem to become dialable. Neither the service being up
# nor the modem being listed is enough: it is exported on the bus as soon as
# it is created and reports state 'unknown' until probing finishes, and a dial
# in that window is refused. An HP lt4132 needed 33s of that, two 10s MBIM
# timeouts of it, so the budget is generous - it is only ever spent on a modem
# that is not answering.
modem_wait_timeout = 60
modem_wait_poll = 0.250

# Markers for WWAN interfaces the operator has taken down with op-mode
# "disconnect interface wwanN". vyos-netlinkd re-dials every configured
# interface that has lost its session, which would otherwise bring the
# interface back up within one reconcile interval and make the disconnect look
# like it never happened. Kept in /run - a manual disconnect is not meant to
# survive a reboot, and a commit re-asserts the configured state too.
admin_disconnect_dir = '/run/vyos-wwan'

def modem_index(ifname: str) -> str:
    """ Return the ModemManager modem index backing an interface, wwan0 -> 0 """
    if not ifname.startswith('wwan'):
        raise ValueError(f'Specified interface "{ifname}" is not a WWAN interface')
    return ifname[len('wwan'):]

def modem_state(index: str) -> str:
    """ ModemManager state of a modem, empty if it cannot be read yet """
    try:
        tmp = cmdl(['mmcli', '--output-keyvalue', '--modem', index])
    except OSError:
        # up but not yet answering on the bus, or no such modem
        return ''

    for line in tmp.splitlines():
        key, _, value = line.partition(':')
        if key.strip() == 'modem.generic.state':
            return value.strip()
    return ''

def start_modem_manager(ifname: str) -> None:
    """ ModemManager is required to dial WWAN connections - a single instance
    serves all modems. Start it if it is not running yet, then wait until the
    modem behind ifname will accept a dial.

    Waiting on the service, or on the modem merely being listed, is not
    enough - both are true long before probing finishes, and dialling then
    leaves the interface without a session until something re-dials it. """
    if not is_systemd_service_active(service_name):
        cmdl(['systemctl', 'start', service_name])

    index = modem_index(ifname)
    counter = int(modem_wait_timeout / modem_wait_poll)
    while counter > 0:
        counter -= 1
        # anything but 'unknown' means probing is done, including 'failed' -
        # waiting out the budget would not improve that, and the dial reports
        # it far better than a timeout here could
        if modem_state(index) not in ('', 'unknown'):
            break
        sleep(modem_wait_poll)

    return None

def connect_options(config: dict) -> str:
    """ Build the mmcli --simple-connect option string for a WWAN interface.

    config is an interface configuration dict as returned by
    get_interface_dict() in conf_mode or op_mode_config_dict() in an op-mode
    context - both are key-mangled the same way, so both are accepted here.
    """
    ip_type = 'ipv4'
    slaac = dict_search('ipv6.address.autoconf', config) != None
    if 'address' in config:
        if 'dhcp' in config['address'] and ('dhcpv6' in config['address'] or slaac):
            ip_type = 'ipv4v6'
        elif 'dhcpv6' in config['address'] or slaac:
            ip_type = 'ipv6'
        elif 'dhcp' in config['address']:
            ip_type = 'ipv4'

    options = f'ip-type={ip_type},apn=' + config['apn']
    if 'authentication' in config:
        options += ',user={username},password={password}'.format(**config['authentication'])

    return options

def _admin_disconnect_marker(ifname: str) -> str:
    return os.path.join(admin_disconnect_dir, f'{ifname}.disconnected')

def set_admin_disconnected(ifname: str) -> None:
    """ Mark a WWAN interface as administratively disconnected, so it is left
    alone by the re-dial pass in vyos-netlinkd """
    # rejects anything that is not a WWAN interface, so a bogus name can never
    # end up creating a file here
    modem_index(ifname)
    os.makedirs(admin_disconnect_dir, exist_ok=True)
    with open(_admin_disconnect_marker(ifname), 'w'):
        pass

def clear_admin_disconnected(ifname: str) -> None:
    """ Take a WWAN interface out of the administratively disconnected state """
    modem_index(ifname)
    try:
        os.unlink(_admin_disconnect_marker(ifname))
    except FileNotFoundError:
        pass

def is_admin_disconnected(ifname: str) -> bool:
    """ True if a WWAN interface was taken down with op-mode "disconnect" and
    has not been connected again since """
    return os.path.exists(_admin_disconnect_marker(ifname))

def modem_disconnect(ifname: str, quiet: bool = False) -> None:
    """ Disconnect every bearer of the modem backing ifname. The number of
    bearers a modem can hold is limited, so we always disconnect before we
    dial again. """
    call(f'mmcli --modem {modem_index(ifname)} --simple-disconnect',
         stdout=DEVNULL if quiet else None,
         stderr=DEVNULL if quiet else None)

def modem_connect(ifname: str, options: str) -> bool:
    """ Dial the modem backing ifname, returns True if the modem connected """
    modem = modem_index(ifname)

    # Some networks only ever admit a single combined IPv4+IPv6 PDN context per
    # APN and reject a standalone IPv6 "Start Network" request outright (QMI
    # CallEndReason ip-version-mismatch) once an IPv4 session already exists for
    # that APN. ModemManager's --simple-connect with ip-type=ipv4v6 opens two
    # separate WDS sessions (one per family) rather than negotiating both
    # together, which is what a normal handset attach does and why this is
    # invisible on most other devices.
    #
    # Pre-negotiating the attach-time PDN type upfront avoids the rejection; the
    # resulting bearer only sets up what the *next* --simple-connect is allowed
    # to request and can't be connected directly, so a failure here isn't fatal
    # - unsupported modems simply proceed to --simple-connect exactly as before.
    if options.partition('ip-type=')[2].partition(',')[0] in ('ipv6', 'ipv4v6'):
        # best effort by definition, so do not report the rejection a modem
        # without attach configuration support answers with on every dial
        call(f'mmcli --modem {modem} --3gpp-set-initial-eps-bearer-settings="{options}"',
             stdout=DEVNULL, stderr=DEVNULL)

    command = f'mmcli --modem {modem} --simple-connect="{options}"'
    return call(command, stdout=DEVNULL) == 0
