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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

from sys import exit

from vyos.config import Config
from vyos.configdep import set_dependents
from vyos.configdep import call_dependents
from vyos.configdict import get_interface_dict
from vyos.configdict import is_node_changed
from vyos.configdict import is_vrf_changed
from vyos.configverify import verify_authentication
from vyos.configverify import verify_interface_exists
from vyos.configverify import verify_mirror_redirect
from vyos.configverify import verify_vrf
from vyos.configverify import verify_mtu_ipv6
from vyos.ifconfig import WWANIf
from vyos.utils.network import is_wwan_connected
from vyos.utils.process import cmdl
from vyos.utils.wwan import clear_admin_disconnected
from vyos.utils.wwan import connect_options
from vyos.utils.wwan import modem_connect
from vyos.utils.wwan import modem_disconnect
from vyos.utils.wwan import service_name
from vyos.utils.wwan import start_modem_manager
from vyos import ConfigError
from vyos import airbag
airbag.enable()

def get_config(config=None):
    """
    Retrieve CLI config as dictionary. Dictionary can never be empty, as at least the
    interface name will be added or a deleted flag
    """
    if config:
        conf = config
    else:
        conf = Config()
    base = ['interfaces', 'wwan']
    ifname, wwan = get_interface_dict(conf, base)

    # We should only terminate the WWAN session if critical parameters change.
    # All parameters that can be changed on-the-fly (like interface description)
    # should not lead to a reconnect!
    tmp = is_node_changed(conf, base + [ifname, 'address'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'apn'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'disable'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'vrf'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'authentication'])
    if tmp: wwan.update({'shutdown_required': {}})

    tmp = is_node_changed(conf, base + [ifname, 'ipv6', 'address', 'autoconf'])
    if tmp: wwan.update({'shutdown_required': {}})

    # We need to know the amount of other WWAN interfaces as ModemManager needs
    # to be started or stopped.
    wwan['other_interfaces'] = conf.get_config_dict([], key_mangling=('-', '_'),
                                                       get_first_key=True,
                                                       no_tag_node_value_mangle=True)

    # This if-clause is just to be sure - it will always evaluate to true
    if ifname in wwan['other_interfaces']:
        del wwan['other_interfaces'][ifname]
    if len(wwan['other_interfaces']) == 0:
        del wwan['other_interfaces']

    # Protocols static arp dependency
    if 'static_arp' in wwan:
        set_dependents('static_arp', conf)

    # Check vrf membership, to ensure firewall is updated
    if is_vrf_changed(conf, ifname):
        set_dependents('firewall', conf)

    return wwan

def verify(wwan):
    if 'deleted' in wwan:
        return None

    ifname = wwan['ifname']
    if not 'apn' in wwan:
        raise ConfigError(f'No APN configured for "{ifname}"!')

    verify_interface_exists(wwan, ifname)
    verify_authentication(wwan)
    verify_vrf(wwan)
    verify_mtu_ipv6(wwan)
    verify_mirror_redirect(wwan)

    return None

def generate(wwan):
    # Nothing to render - re-dialling a session that was lost (e.g. during RF
    # signal loss) is owned by vyos-netlinkd, which reconciles every configured
    # WWAN interface against ModemManager on its own.
    return None

def apply(wwan):
    # A commit re-asserts the configured state, so it also takes the interface
    # out of the administratively disconnected state that op-mode "disconnect
    # interface wwanN" put it in.
    clear_admin_disconnected(wwan['ifname'])

    # ModemManager is required to dial WWAN connections - one instance is
    # required to serve all modems. Activate ModemManager on first invocation
    # of any WWAN interface.
    start_modem_manager()

    if 'shutdown_required' in wwan or (not is_wwan_connected(wwan['ifname'])):
        # Number of bearers is limited - always disconnect first
        modem_disconnect(wwan['ifname'])

    w = WWANIf(wwan['ifname'])

    # We cannot proceed with the configuration if the modem is not detected - so
    # we bail out and let vyos-netlinkd re-dial once the modem has shown up.
    if not w.exists(wwan['ifname']):
        return None

    if 'deleted' in wwan or 'disable' in wwan:
        w.remove()

        # We are the last WWAN interface - there are no other WWAN interfaces
        # remaining, thus we can stop ModemManager and free resources.
        if 'other_interfaces' not in wwan:
            cmdl(['systemctl', 'stop', service_name])

        # run the dependents
        call_dependents()

        return None

    if 'shutdown_required' in wwan or (not is_wwan_connected(wwan['ifname'])):
        modem_connect(wwan['ifname'], connect_options(wwan))

    w.update(wwan)

    # run the dependents
    call_dependents()

    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
