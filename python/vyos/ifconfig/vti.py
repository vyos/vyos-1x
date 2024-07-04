# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos.ifconfig.interface import Interface
from vyos.utils.dict import dict_search
from vyos.utils.vti_updown_db import vti_updown_db_exists, open_vti_updown_db_readonly

@Interface.register
class VTIIf(Interface):
    iftype = 'vti'
    definition = {
        **Interface.definition,
        **{
            'section': 'vti',
            'prefixes': ['vti', ],
        },
    }

    def __init__(self, ifname, **kwargs):
        self.bypass_vti_updown_db = kwargs.pop("bypass_vti_updown_db", False)
        super().__init__(ifname, **kwargs)

    def _create(self):
        # This table represents a mapping from VyOS internal config dict to
        # arguments used by iproute2. For more information please refer to:
        # - https://man7.org/linux/man-pages/man8/ip-link.8.html
        # - https://man7.org/linux/man-pages/man8/ip-tunnel.8.html
        mapping = {
            'source_interface' : 'dev',
        }
        if_id = self.ifname.lstrip('vti')
        # The key defaults to 0 and will match any policies which similarly do
        # not have a lookup key configuration - thus we shift the key by one
        # to also support a vti0 interface
        if_id = str(int(if_id) +1)
        cmd = f'ip link add {self.ifname} type xfrm if_id {if_id}'
        for vyos_key, iproute2_key in mapping.items():
            # dict_search will return an empty dict "{}" for valueless nodes like
            # "parameters.nolearning" - thus we need to test the nodes existence
            # by using isinstance()
            tmp = dict_search(vyos_key, self.config)
            if isinstance(tmp, dict):
                cmd += f' {iproute2_key}'
            elif tmp != None:
                cmd += f' {iproute2_key} {tmp}'

        self._cmd(cmd.format(**self.config))

        # interface is always A/D down. It needs to be enabled explicitly
        self.set_interface('admin_state', 'down')

    def set_admin_state(self, state):
        """
        Set interface administrative state to be 'up' or 'down'.

        The interface will only be brought 'up' if ith is attached to an
        active ipsec site-to-site connection or remote access connection.
        """
        if state == 'down' or self.bypass_vti_updown_db:
            super().set_admin_state(state)
        elif vti_updown_db_exists():
            with open_vti_updown_db_readonly() as db:
                if db.wantsInterfaceUp(self.ifname):
                    super().set_admin_state(state)

    def get_mac(self):
        """ Get a synthetic MAC address. """
        return self.get_mac_synthetic()
