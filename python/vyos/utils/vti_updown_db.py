# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.utils.locking import Lock

VTI_WANT_UP_IFLIST = '/tmp/ipsec_vti_interfaces'
VTI_UPDOWN_LOCK_NAME = 'ipsec_vti_updown'

def vti_updown_db_exists():
    """ Returns true if the database exists """
    return os.path.exists(VTI_WANT_UP_IFLIST)

@contextmanager
def _vti_updown_db_lock():
    """Serialise access to the VTI up/down DB across the concurrent updown-hook
    invocations (one per VTI) that strongSwan fires during a coordinated rekey,
    which would otherwise lost-update the shared state file."""
    lock = Lock(VTI_UPDOWN_LOCK_NAME)
    lock.acquire()  # timeout=0 -> block until acquired
    try:
        yield
    finally:
        lock.release()


@contextmanager
def open_vti_updown_db_for_create_or_update():
    """ Opens the database for reading and writing, creating the database if it does not exist """
    with _vti_updown_db_lock():
        mode = 'r+' if vti_updown_db_exists() else 'x+'
        with open(VTI_WANT_UP_IFLIST, mode) as f:
            yield VTIUpDownDB(f)

@contextmanager
def open_vti_updown_db_for_update():
    """ Opens the database for reading and writing, returning an error if it does not exist """
    with _vti_updown_db_lock():
        with open(VTI_WANT_UP_IFLIST, 'r+') as f:
            yield VTIUpDownDB(f)

@contextmanager
def open_vti_updown_db_readonly():
    """Opens the database for reading. Yields None if the database does not exist."""
    with _vti_updown_db_lock():
        if not vti_updown_db_exists():
            yield None
            return
        with open(VTI_WANT_UP_IFLIST, 'r') as f:
            yield VTIUpDownDB(f)

def remove_vti_updown_db():
    """Brings down any interfaces referenced by the database and removes the database, if it exists."""
    with _vti_updown_db_lock():
        if not vti_updown_db_exists():
            return
        # We hold the lock already; open the file directly rather than via the
        # locking context manager to avoid re-acquiring (which would deadlock).
        with open(VTI_WANT_UP_IFLIST, 'r+') as f:
            db = VTIUpDownDB(f)
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
    # Connection entries are a multiset: the same ifspec is stored once per
    # established CHILD_SA, because a connection can transiently have more
    # than one -- when the peer establishes a new SA before the old one has
    # timed out. The interface must stay up until the last of them is gone.
    # Persistent entries remain unique.
    #
    # The count is exact only while every up-client is eventually matched by a
    # down-client, which holds because the updown plugin implements child_updown
    # and is not invoked for rekeys of either the IKE_SA or the CHILD_SA. Should
    # a teardown be lost anyway - e.g., charon killed outright - the leaked
    # occurrence holds the interface up rather than dropping one that is still
    # carrying traffic, and it does not outlive the daemon: this file lives in
    # /tmp, and remove_vti_updown_db() discards it when the IPsec configuration
    # goes away.
    #
    # The configuration tree and ipsec daemon connection up-down hook
    # modify this file as needed and use it to determine when a
    # particular event or configuration change should lead to changing
    # the interface state.

    def __init__(self, f):
        self._fileHandle = f
        self._ifspecs = [
            entry.strip()
            for entry in f.read().split(" ")
            if entry and not entry.isspace()
        ]
        self._ifsUp = set()
        self._ifsDown = set()

    def add(self, interface, connection = None, protocol = None):
        """
        Adds a new entry to the DB.

        If an interface name, connection name, and protocol are supplied,
        creates a connection entry. Connection entries are counted, so one is
        stored per established CHILD_SA even when they share an ifspec.

        If only an interface name is specified, creates a persistent entry
        for the given interface. Persistent entries are not counted.
        """
        ifspec = f"{interface}:{connection}:{protocol}" if (connection is not None and protocol is not None) else interface
        if ':' not in ifspec and ifspec in self._ifspecs:
            return

        self._ifspecs.append(ifspec)
        self._ifsUp.add(interface)
        self._ifsDown.discard(interface)

    def remove(self, interface, connection = None, protocol = None):
        """
        Removes a matching entry from the DB.

        For a connection entry a single occurrence is removed, so the interface
        is only brought down once the last CHILD_SA using it has gone away.

        If no matching entry can be found, the operation returns successfully.
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
        updated_ifspecs = [
            ifspec for ifspec in self._ifspecs if ifspec.split(':')[0] in interface_list
        ]
        removed_ifspecs = [
            ifspec
            for ifspec in self._ifspecs
            if ifspec.split(':')[0] not in interface_list
        ]
        self._ifspecs = updated_ifspecs
        interfaces_to_bring_down = [ifspec.split(':')[0] for ifspec in removed_ifspecs]
        self._ifsDown.update(interfaces_to_bring_down)
        self._ifsUp.difference_update(interfaces_to_bring_down)

    def setPersistentInterfaces(self, interface_list):
        """ Updates the set of persistently up interfaces to match the given list """
        new_persistent_interfaces = set(interface_list)
        current_persistent_interfaces = set([ifspec for ifspec in self._ifspecs if ':' not in ifspec])
        added_persistent_interfaces = new_persistent_interfaces - current_persistent_interfaces
        removed_persistent_interfaces = current_persistent_interfaces - new_persistent_interfaces

        for interface in added_persistent_interfaces:
            self.add(interface)

        for interface in removed_persistent_interfaces:
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
            vti_link = get_interface_config(interface) or {}
            vti_link_up = (vti_link['operstate'] != 'DOWN' if 'operstate' in vti_link else False)
            if vti_link_up:
                call(f'sudo ip link set {interface} down')
                syslog(f'Interface {interface} is admin down ...')

        self._ifsDown.clear()

        for interface in self._ifsUp:
            vti_link = get_interface_config(interface) or {}
            vti_link_up = (vti_link['operstate'] != 'DOWN' if 'operstate' in vti_link else False)
            if not vti_link_up:
                vti = interface_dict_supplier(interface)
                if 'disable' not in vti:
                    tmp = VTIIf(interface, bypass_vti_updown_db = True)
                    tmp.update(vti)
                    syslog(f'Interface {interface} is admin up ...')

        self._ifsUp.clear()
