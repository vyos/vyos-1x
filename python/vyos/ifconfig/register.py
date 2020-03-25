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
            return cls._prefixes[name].definition['section']
        return ''
 
    @classmethod
    def klass(cls, name, vlan=True):
        name = cls._basename(name, vlan)
        if name in cls._prefixes:
            return cls._prefixes[name]
        raise ValueError(f'No type found for interface name: {name}')

    @classmethod
    def _listing (cls,section=''):
        interfaces = netifaces.interfaces()

        for ifname in interfaces:
            # XXX: Temporary hack as vti and input are not yet moved from vyatta to vyos
            if ifname.startswith('vti') or ifname.startswith('input'):
                yield ifname
                continue

            ifsection = cls.section(ifname)
            if not ifsection:
                continue

            if section and ifsection != section:
                continue

            yield ifname

    @classmethod
    def listing(cls, section=''):
        return list(cls._listing(section))


# XXX: TODO - limit name for VRF interfaces

