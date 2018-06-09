import re
import json

import netifaces


intf_type_data_file = '/usr/share/vyos/interface-types.json'

def list_interfaces():
    interfaces = netifaces.interfaces()

    # Remove "fake" interfaces associated with drivers
    for i in ["dummy0", "ip6tnl0", "tunl0", "ip_vti0", "ip6_vti0"]:
        try:
            interfaces.remove(i)
        except ValueError:
            pass

    return interfaces

def list_interfaces_of_type(typ):
    with open(intf_type_data_file, 'r') as f:
        types_data = json.load(f)

    all_intfs = list_interfaces()
    if not (typ in types_data.keys()):
        raise ValueError("Unknown interface type: {0}".format(typ))
    else:
        r = re.compile('^{0}\d+'.format(types_data[typ]))
        return list(filter(lambda i: re.match(r, i), all_intfs))
