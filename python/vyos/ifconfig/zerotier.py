# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or modify
# it under the terms of the GNU Lesser General Public License as published
# by the Free Software Foundation; either version 2.1 of the License, or
# (at your option) any later version.

from vyos.ifconfig.interface import Interface


@Interface.register
class ZeroTierIf(Interface):
    iftype = 'zerotier'
    definition = {
        **Interface.definition,
        **{
            'section': 'zerotier',
            'prefixes': ['zt'],
            'bridgeable': True,
        },
    }

    def _create(self):
        raise RuntimeError('ZeroTier interfaces are created by ZeroTier configuration')
