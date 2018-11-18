#!/usr/bin/env python3

import re
import subprocess

import tabulate

def parse_conn_spec(s):
    # Example: ESTABLISHED 14 seconds ago, 10.0.0.2[foo]...10.0.0.1[10.0.0.1]
    return re.search(r'.*ESTABLISHED\s+(.*)ago,\s(.*)\[(.*)\]\.\.\.(.*)\[(.*)\].*', s).groups()

def parse_ike_line(s):
    # Example: 3DES_CBC/HMAC_MD5_96/MODP_1024, 0 bytes_i, 0 bytes_o, rekeying in 45 minutes
    try:
        return re.search(r'.*:\s+(.*)\/(.*)\/(.*),\s+(\d+)\s+bytes_i,\s+(\d+)\s+bytes_o,\s+rekeying', s).groups()
    except AttributeError:
        return (None, None, None, None, None)


# Get a list of all configured connections
with open('/etc/ipsec.conf', 'r') as f:
    config = f.read()
    connections = re.findall(r'conn\s([^\s]+)\s*\n', config)
    connections = list(filter(lambda s: s != '%default', connections))

status_data = []

for conn in connections:
    status = subprocess.check_output("ipsec statusall {0}".format(conn), shell=True).decode()
    if re.search(r'no match', status):
        status_line = [conn, "down", None, None, None, None, None]
    else:
        try:
            time, _, _, ip, id = parse_conn_spec(status)
            if ip == id:
                id = None
            enc, hash, dh, bytes_in, bytes_out = parse_ike_line(status)
            status_line = [conn, "up", time, "{0}/{1}".format(bytes_in, bytes_out), ip, id, "{0}/{1}/{2}".format(enc, hash, dh)]
        except Exception as e:
            print(status)
            raise e
            status_line = [conn, None, None, None, None, None]

    status_line = list(map(lambda x: "N/A" if x is None else x, status_line))
    status_data.append(status_line)

headers = ["Connection", "State", "Up", "Bytes In/Out", "Remote address", "Remote ID", "Proposal"]
output = tabulate.tabulate(status_data, headers)
print(output)
