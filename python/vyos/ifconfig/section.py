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
    def _basename (cls, name, vlan):
        """
        remove the number at the end of interface name
        name: name of the interface
        vlan: if vlan is True, do not stop at the vlan number
        """
        name = name.rstrip('0123456789')
        name = name.rstrip('.')
        if vlan:
            name = name.rstrip('0123456789.')
        return name

    @classmethod
    def section(cls, name, vlan=True):
        """
        return the name of a section an interface should be under
        name: name of the interface (eth0, dum1, ...)
        vlan: should we try try to remove the VLAN from the number
        """
        name = cls._basename(name, vlan)

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
    def klass(cls, name, vlan=True):
        name = cls._basename(name, vlan)
        if name in cls._prefixes:
            return cls._prefixes[name]
        raise ValueError(f'No type found for interface name: {name}')

    @classmethod
    def _intf_under_section (cls,section=''):
        """
        return a generator with the name of the configured interface
        which are under a section
        """
        interfaces = netifaces.interfaces()

        for ifname in interfaces:
            ifsection = cls.section(ifname)
            if not ifsection:
                continue

            if section and ifsection != section:
                continue

            yield ifname

    @classmethod
    def interfaces(cls, section=''):
        """
        return a list of the name of the configured interface which are under a section
        if no section is provided, then it returns all configured interfaces
        """
        return list(cls._intf_under_section(section))

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
