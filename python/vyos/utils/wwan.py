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

from time import sleep

from vyos.utils.dict import dict_search
from vyos.utils.process import call
from vyos.utils.process import cmdl
from vyos.utils.process import DEVNULL
from vyos.utils.process import is_systemd_service_active

service_name = 'ModemManager.service'

# Bounded wait for a modem to appear after ModemManager has been started. The
# service being up is not enough - the modem is only dialable once it has been
# probed and exported on the bus, which takes a moment longer.
modem_wait_timeout = 25
modem_wait_poll = 0.250

def modem_index(ifname: str) -> str:
    """ Return the ModemManager modem index backing an interface, wwan0 -> 0 """
    if not ifname.startswith('wwan'):
        raise ValueError(f'Specified interface "{ifname}" is not a WWAN interface')
    return ifname[len('wwan'):]

def start_modem_manager() -> None:
    """ ModemManager is required to dial WWAN connections - a single instance
    serves all modems. Start it if it is not running yet and wait until a modem
    has been detected, so a dial that follows does not race the probing. """
    if is_systemd_service_active(service_name):
        return None

    cmdl(['systemctl', 'start', service_name])

    counter = int(modem_wait_timeout / modem_wait_poll)
    while counter > 0:
        counter -= 1
        try:
            tmp = cmdl(['mmcli', '-L'])
        except OSError:
            # ModemManager is up but not yet answering on the bus - keep
            # polling, this is expected for the first moments after start.
            tmp = ''
        if tmp and tmp != 'No modems were found':
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

def modem_disconnect(ifname: str) -> None:
    """ Disconnect every bearer of the modem backing ifname. The number of
    bearers a modem can hold is limited, so we always disconnect before we
    dial again. """
    call(f'mmcli --modem {modem_index(ifname)} --simple-disconnect')

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
