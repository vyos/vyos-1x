# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

import netifaces


class Register:
    # the known interface prefixes
    _prefixes = {}

    # class need to define: definition['prefixes']
    # the interface prefixes declared by a class used to name interface with
    # prefix[0-9]*(\.[0-9]+)?(\.[0-9]+)?, such as lo, eth0 or eth0.1.2

    @classmethod
    def register(cls, klass):
        if not klass.definition.get('prefixes',[]):
            raise RuntimeError(f'valid interface prefixes not defined for {klass.__name__}')

        for ifprefix in klass.definition['prefixes']:
            if ifprefix in cls._prefixes:
                raise RuntimeError(f'only one class can be registered for prefix "{ifprefix}" type')
            cls._prefixes[ifprefix] = klass

        return klass

    @classmethod
    def _basename (cls, name, vlan):
        # remove number from interface name
        name = name.rstrip('0123456789')
        name = name.rstrip('.')
        if vlan:
            name = name.rstrip('0123456789')
        return name

    @classmethod
    def section(cls, name, vlan=True):
        # return the name of a section an interface should be under
        name = cls._basename(name, vlan)

        # XXX: To leave as long as vti and input are not moved to vyos
        if name == 'vti':
            return 'vti'
        if name == 'ifb':
            return 'input'

        if name in cls._prefixes:
            return cls._prefixes[name].defintion['section']
        return ''
 
    @classmethod
    def klass(cls, name, vlan=True):
        name = cls._basename(name, vlan)
        if name in cls._prefixes:
            return cls._prefixes[name]
        raise ValueError(f'No type found for interface name: {name}')

    @classmethod
    def _listing (cls):
        interfaces = netifaces.interfaces()

        for ifname in interfaces:
            if '@' in ifname:
                # Tunnels: sit0@NONE, gre0@NONE, gretap0@NONE, erspan0@NONE, tunl0@NONE, ip6tnl0@NONE, ip6gre0@NONE
                continue

            # XXX: Temporary hack as vti and input are not yet moved from vyatta to vyos
            if ifname.startswith('vti') or ifname.startswith('input'):
                yield ifname
                continue

            if not cls.section(ifname):
                continue
            yield ifname

    @classmethod
    def listing(cls, section=''):
        if not section:
            return list(cls._listing())
        return [_ for _ in cls._listing() if cls._basename(_,False) in self.prefixes]


# XXX: TODO - limit name for VRF interfaces

