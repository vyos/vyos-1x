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

import re
import netifaces


class Section:
    # the known interface prefixes
    _prefixes = {}
    _classes = []

    # class need to define: definition['prefixes']
    # the interface prefixes declared by a class used to name interface with
    # prefix[0-9]*(\.[0-9]+)?(\.[0-9]+)?, such as lo, eth0 or eth0.1.2

    @classmethod
    def register(cls, klass):
        """
        A function to use as decorator the interfaces classes
        It register the prefix for the interface (eth, dum, vxlan, ...)
        with the class which can handle it (EthernetIf, DummyIf,VXLANIf, ...)
        """
        if not klass.definition.get('prefixes',[]):
            raise RuntimeError(f'valid interface prefixes not defined for {klass.__name__}')

        cls._classes.append(klass)

        for ifprefix in klass.definition['prefixes']:
            if ifprefix in cls._prefixes:
                raise RuntimeError(f'only one class can be registered for prefix "{ifprefix}" type')
            cls._prefixes[ifprefix] = klass

        return klass

    @classmethod
    def _basename(cls, name, vlan, vrrp):
        """
        remove the number at the end of interface name
        name: name of the interface
        vlan: if vlan is True, do not stop at the vlan number
        """
        if vrrp:
            name = re.sub(r'\d(\d|v|\.)*$', '', name)
        elif vlan:
            name = re.sub(r'\d(\d|\.)*$', '', name)
        else:
            name = re.sub(r'\d+$', '', name)
        return name

    @classmethod
    def section(cls, name, vlan=True, vrrp=True):
        """
        return the name of a section an interface should be under
        name: name of the interface (eth0, dum1, ...)
        vlan: should we try try to remove the VLAN from the number
        """
        name = cls._basename(name, vlan, vrrp)

        if name in cls._prefixes:
            return cls._prefixes[name].definition['section']
        return ''

    @classmethod
    def sections(cls):
        """
        return all the sections we found under 'set interfaces'
        """
        return list(set([cls._prefixes[_].definition['section'] for _ in cls._prefixes]))

    @classmethod
    def klass(cls, name, vlan=True, vrrp=True):
        name = cls._basename(name, vlan, vrrp)
        if name in cls._prefixes:
            return cls._prefixes[name]
        raise ValueError(f'No type found for interface name: {name}')

    @classmethod
    def _intf_under_section (cls,section='',vlan=True):
        """
        return a generator with the name of the configured interface
        which are under a section
        """
        interfaces = netifaces.interfaces()

        for ifname in interfaces:
            ifsection = cls.section(ifname)
            if not ifsection and not ifname.startswith('vrrp'):
                continue

            if section and ifsection != section:
                continue

            if vlan == False and '.' in ifname:
                continue

            yield ifname

    @classmethod
    def _sort_interfaces(cls, generator):
        """
        return a list of the sorted interface by number, vlan, qinq
        """
        def key(ifname):
            value = 0
            parts = re.split(r'([^0-9]+)([0-9]+)[.]?([0-9]+)?[.]?([0-9]+)?', ifname)
            length = len(parts)
            name = parts[1] if length >= 3 else parts[0]
            # the +1 makes sure eth0.0.0 after eth0.0
            number = int(parts[2]) + 1 if length >= 4 and parts[2] is not None else 0
            vlan = int(parts[3]) + 1 if length >= 5 and parts[3] is not None else 0
            qinq = int(parts[4]) + 1 if length >= 6 and parts[4] is not None else 0

            # so that "lo" (or short names) are handled (as "loa")
            for n in (name + 'aaa')[:3]:
                value *= 100
                value += (ord(n) - ord('a'))
            value += number
            # vlan are 16 bits, so this can not overflow
            value = (value << 16) + vlan
            value = (value << 16) + qinq
            return value

        l = list(generator)
        l.sort(key=key)
        return l

    @classmethod
    def interfaces(cls, section='', vlan=True):
        """
        return a list of the name of the configured interface which are under a section
        if no section is provided, then it returns all configured interfaces.
        If vlan is True, also Vlan subinterfaces will be returned
        """

        return cls._sort_interfaces(cls._intf_under_section(section, vlan))

    @classmethod
    def _intf_with_feature(cls, feature=''):
        """
        return a generator with the name of the configured interface which have
        a particular feature set in their definition such as:
        bondable, broadcast, bridgeable, ...
        """
        for klass in cls._classes:
            if klass.definition[feature]:
                yield klass.definition['section']

    @classmethod
    def feature(cls, feature=''):
        """
        return list with the name of the configured interface which have
        a particular feature set in their definition such as:
        bondable, broadcast, bridgeable, ...
        """
        return list(cls._intf_with_feature(feature))

    @classmethod
    def reserved(cls):
        """
        return list with the interface name prefixes
        eth, lo, vxlan, dum, ...
        """
        return list(cls._prefixes.keys())

    @classmethod
    def get_config_path(cls, name):
        """
        get config path to interface with .vif or .vif-s.vif-c
        example: eth0.1.2 -> 'ethernet eth0 vif-s 1 vif-c 2'
        Returns False if interface name is invalid (not found in sections)
        """
        sect = cls.section(name)
        if sect:
            splinterface = name.split('.')
            intfpath = f'{sect} {splinterface[0]}'
            if len(splinterface) == 2:
                intfpath += f' vif {splinterface[1]}'
            elif len(splinterface) == 3:
                intfpath += f' vif-s {splinterface[1]} vif-c {splinterface[2]}'
            return intfpath
        else:
            return False
