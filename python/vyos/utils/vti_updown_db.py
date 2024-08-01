# Copyright 2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from contextlib import contextmanager
from syslog import syslog

VTI_WANT_UP_IFLIST = '/tmp/ipsec_vti_interfaces'

def vti_updown_db_exists():
    """ Returns true if the database exists """
    return os.path.exists(VTI_WANT_UP_IFLIST)

@contextmanager
def open_vti_updown_db_for_create_or_update():
    """ Opens the database for reading and writing, creating the database if it does not exist """
    if vti_updown_db_exists():
        f = open(VTI_WANT_UP_IFLIST, 'r+')
    else:
        f = open(VTI_WANT_UP_IFLIST, 'x+')
    try:
        db = VTIUpDownDB(f)
        yield db
    finally:
        f.close()

@contextmanager
def open_vti_updown_db_for_update():
    """ Opens the database for reading and writing, returning an error if it does not exist """
    f = open(VTI_WANT_UP_IFLIST, 'r+')
    try:
        db = VTIUpDownDB(f)
        yield db
    finally:
        f.close()

@contextmanager
def open_vti_updown_db_readonly():
    """ Opens the database for reading, returning an error if it does not exist """
    f = open(VTI_WANT_UP_IFLIST, 'r')
    try:
        db = VTIUpDownDB(f)
        yield db
    finally:
        f.close()

def remove_vti_updown_db():
    """ Brings down any interfaces referenced by the database and removes the database """
    # We need to process the DB first to bring down any interfaces still up
    with open_vti_updown_db_for_update() as db:
        db.removeAllOtherInterfaces([])
        # this usage of commit will only ever bring down interfaces,
        # do not need to provide a functional interface dict supplier
        db.commit(lambda _: None)

    os.unlink(VTI_WANT_UP_IFLIST)

class VTIUpDownDB:
    # The VTI Up-Down DB is a text-based database of space-separated "ifspecs".
    #
    # ifspecs can come in one of the two following formats:
    #
    # persistent format: <interface name>
    # indicates the named interface should always be up.
    #
    # connection format: <interface name>:<connection name>:<protocol>
    # indicates the named interface wants to be up due to an established
    # connection <connection name> using the <protocol> protocol.
    #
    # The configuration tree and ipsec daemon connection up-down hook
    # modify this file as needed and use it to determine when a
    # particular event or configuration change should lead to changing
    # the interface state.

    def __init__(self, f):
        self._fileHandle = f
        self._ifspecs = set([entry.strip() for entry in f.read().split(" ") if entry and not entry.isspace()])
        self._ifsUp = set()
        self._ifsDown = set()

    def add(self, interface, connection = None, protocol = None):
        """
        Adds a new entry to the DB.

        If an interface name, connection name, and protocol are supplied,
        creates a connection entry.

        If only an interface name is specified, creates a persistent entry
        for the given interface.
        """
        ifspec = f"{interface}:{connection}:{protocol}" if (connection is not None and protocol is not None) else interface
        if ifspec not in self._ifspecs:
            self._ifspecs.add(ifspec)
            self._ifsUp.add(interface)
            self._ifsDown.discard(interface)

    def remove(self, interface, connection = None, protocol = None):
        """
        Removes a matching entry from the DB.

        If no matching entry can be fonud, the operation returns successfully.
        """
        ifspec = f"{interface}:{connection}:{protocol}" if (connection is not None and protocol is not None) else interface
        if ifspec in self._ifspecs:
            self._ifspecs.remove(ifspec)
            interface_remains = False
            for ifspec in self._ifspecs:
                if ifspec.split(':')[0] == interface:
                    interface_remains = True

            if not interface_remains:
                self._ifsDown.add(interface)
                self._ifsUp.discard(interface)

    def wantsInterfaceUp(self, interface):
        """ Returns whether the DB contains at least one entry referencing the given interface """
        for ifspec in self._ifspecs:
                if ifspec.split(':')[0] == interface:
                    return True

        return False

    def removeAllOtherInterfaces(self, interface_list):
        """ Removes all interfaces not included in the given list from the DB """
        updated_ifspecs = set([ifspec for ifspec in self._ifspecs if ifspec.split(':')[0] in interface_list])
        removed_ifspecs = self._ifspecs - updated_ifspecs
        self._ifspecs = updated_ifspecs
        interfaces_to_bring_down = [ifspec.split(':')[0] for ifspec in removed_ifspecs]
        self._ifsDown.update(interfaces_to_bring_down)
        self._ifsUp.difference_update(interfaces_to_bring_down)

    def setPersistentInterfaces(self, interface_list):
        """ Updates the set of persistently up interfaces to match the given list """
        new_presistent_interfaces = set(interface_list)
        current_presistent_interfaces = set([ifspec for ifspec in self._ifspecs if ':' not in ifspec])
        added_presistent_interfaces = new_presistent_interfaces - current_presistent_interfaces
        removed_presistent_interfaces = current_presistent_interfaces - new_presistent_interfaces

        for interface in added_presistent_interfaces:
            self.add(interface)

        for interface in removed_presistent_interfaces:
            self.remove(interface)

    def commit(self, interface_dict_supplier):
        """
        Writes the DB to disk and brings interfaces up and down as needed.

        Only interfaces referenced by entries modified in this DB session
        are manipulated. If an interface is called to be brought up, the
        provided interface_config_supplier function is invoked and expected
        to return the config dictionary for the interface.
        """
        from vyos.ifconfig import VTIIf
        from vyos.utils.process import call
        from vyos.utils.network import get_interface_config

        self._fileHandle.seek(0)
        self._fileHandle.write(' '.join(self._ifspecs))
        self._fileHandle.truncate()

        for interface in self._ifsDown:
            vti_link = get_interface_config(interface)
            vti_link_up = (vti_link['operstate'] != 'DOWN' if 'operstate' in vti_link else False)
            if vti_link_up:
                call(f'sudo ip link set {interface} down')
                syslog(f'Interface {interface} is admin down ...')

        self._ifsDown.clear()

        for interface in self._ifsUp:
            vti_link = get_interface_config(interface)
            vti_link_up = (vti_link['operstate'] != 'DOWN' if 'operstate' in vti_link else False)
            if not vti_link_up:
                vti = interface_dict_supplier(interface)
                if 'disable' not in vti:
                    tmp = VTIIf(interface, bypass_vti_updown_db = True)
                    tmp.update(vti)
                    syslog(f'Interface {interface} is admin up ...')

        self._ifsUp.clear()
