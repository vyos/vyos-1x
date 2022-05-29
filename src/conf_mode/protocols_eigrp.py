#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    vrf = None
    if len(argv) > 1:
        vrf = argv[1]

    base_path = ['protocols', 'eigrp']

    # eqivalent of the C foo ? 'a' : 'b' statement
    base = vrf and ['vrf', 'name', vrf, 'protocols', 'eigrp'] or base_path
    eigrp = conf.get_config_dict(base, key_mangling=('-', '_'),
                               get_first_key=True, no_tag_node_value_mangle=True)

    # Assign the name of our VRF context. This MUST be done before the return
    # statement below, else on deletion we will delete the default instance
    # instead of the VRF instance.
    if vrf: eigrp.update({'vrf' : vrf})

    if not conf.exists(base):
        eigrp.update({'deleted' : ''})
        if not vrf:
            # We are running in the default VRF context, thus we can not delete
            # our main EIGRP instance if there are dependent EIGRP VRF instances.
            eigrp['dependent_vrfs'] = conf.get_config_dict(['vrf', 'name'],
                key_mangling=('-', '_'),
                get_first_key=True,
                no_tag_node_value_mangle=True)

        return eigrp

    # We also need some additional information from the config, prefix-lists
    # and route-maps for instance. They will be used in verify().
    #
    # XXX: one MUST always call this without the key_mangling() option! See
    # vyos.configverify.verify_common_route_maps() for more information.
    tmp = conf.get_config_dict(['policy'])
    # Merge policy dict into "regular" config dict
    eigrp = dict_merge(tmp, eigrp)

    import pprint
    pprint.pprint(eigrp)
    return eigrp

def verify(eigrp):
    pass

def generate(eigrp):
    pass

def apply(eigrp):
    pass

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
