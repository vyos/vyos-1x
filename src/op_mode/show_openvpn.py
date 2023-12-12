#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import os
import jinja2
import argparse

from sys import exit
from vyos.config import Config

outp_tmpl = """
{% if clients %}
OpenVPN status on {{ intf }}

Client CN       Remote Host            Tunnel IP        Local Host            TX bytes    RX bytes   Connected Since
---------       -----------            ---------        ----------            --------    --------   ---------------
{% for c in clients %}
{{ "%-15s"|format(c.name) }}  {{ "%-21s"|format(c.remote) }}  {{ "%-15s"|format(c.tunnel) }}  {{ "%-21s"|format(local) }} {{ "%-9s"|format(c.tx_bytes) }}   {{ "%-9s"|format(c.rx_bytes) }}  {{ c.online_since }}
{% endfor %}
{% endif %}
"""

def bytes2HR(size):
    # we need to operate in integers
    size = int(size)

    suff = ['B', 'KB', 'MB', 'GB', 'TB']
    suffIdx = 0

    while size > 1024:
        # incr. suffix index
        suffIdx += 1
        # divide
        size = size/1024.0

    output="{0:.1f} {1}".format(size, suff[suffIdx])
    return output

def get_vpn_tunnel_address(peer, interface):
    lst = []
    status_file = '/var/run/openvpn/{}.status'.format(interface)

    with open(status_file, 'r') as f:
        lines = f.readlines()
        for line in lines:
            if peer in line:
                lst.append(line)

        # filter out subnet entries
        lst = [l for l in lst[1:] if '/' not in l.split(',')[0]]

        if lst:
            tunnel_ip = lst[0].split(',')[0]
            return tunnel_ip

        return 'n/a'

def get_status(mode, interface):
    status_file = '/var/run/openvpn/{}.status'.format(interface)
    # this is an empirical value - I assume we have no more then 999999
    # current OpenVPN connections
    routing_table_line = 999999

    data = {
        'mode': mode,
        'intf': interface,
        'local': 'N/A',
        'date': '',
        'clients': [],
    }

    if not os.path.exists(status_file):
        return data

    with open(status_file, 'r') as f:
        lines = f.readlines()
        for line_no, line in enumerate(lines):
            # remove trailing newline character first
            line = line.rstrip('\n')

            # check first line header
            if line_no == 0:
                if mode == 'server':
                    if not line == 'OpenVPN CLIENT LIST':
                        raise NameError('Expected "OpenVPN CLIENT LIST"')
                else:
                    if not line == 'OpenVPN STATISTICS':
                        raise NameError('Expected "OpenVPN STATISTICS"')

                continue

            # second line informs us when the status file has been last updated
            if line_no == 1:
                data['date'] = line.lstrip('Updated,').rstrip('\n')
                continue

            if mode == 'server':
                # followed by line3 giving output information and the actual output data
                #
                # Common Name,Real Address,Bytes Received,Bytes Sent,Connected Since
                # client1,172.18.202.10:55904,2880587,2882653,Fri Aug 23 16:25:48 2019
                # client3,172.18.204.10:41328,2850832,2869729,Fri Aug 23 16:25:43 2019
                # client2,172.18.203.10:48987,2856153,2871022,Fri Aug 23 16:25:45 2019
                if (line_no >= 3) and (line_no < routing_table_line):
                    # indicator that there are no more clients and we will continue with the
                    # routing table
                    if line == 'ROUTING TABLE':
                        routing_table_line = line_no
                        continue

                    client = {
                        'name': line.split(',')[0],
                        'remote': line.split(',')[1],
                        'rx_bytes': bytes2HR(line.split(',')[2]),
                        'tx_bytes': bytes2HR(line.split(',')[3]),
                        'online_since': line.split(',')[4]
                    }
                    client["tunnel"] = get_vpn_tunnel_address(client['remote'], interface)
                    data['clients'].append(client)
                    continue
            else:
                if line_no == 2:
                    client = {
                        'name': 'N/A',
                        'remote': 'N/A',
                        'rx_bytes': bytes2HR(line.split(',')[1]),
                        'tx_bytes': '',
                        'online_since': 'N/A'
                    }
                    continue

                if line_no == 3:
                    client['tx_bytes'] = bytes2HR(line.split(',')[1])
                    data['clients'].append(client)
                    break

    return data

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('-m', '--mode', help='OpenVPN operation mode (server, client, site-2-site)', required=True)

    args = parser.parse_args()

    # Do nothing if service is not configured
    config = Config()
    if len(config.list_effective_nodes('interfaces openvpn')) == 0:
        print("No OpenVPN interfaces configured")
        exit(0)

    # search all OpenVPN interfaces and add those with a matching mode to our
    # interfaces list
    interfaces = []
    for intf in config.list_effective_nodes('interfaces openvpn'):
        # get interface type (server, client, site-to-site)
        mode = config.return_effective_value('interfaces openvpn {} mode'.format(intf))
        if args.mode == mode:
            interfaces.append(intf)

    for intf in interfaces:
        data = get_status(args.mode, intf)
        local_host = config.return_effective_value('interfaces openvpn {} local-host'.format(intf))
        local_port = config.return_effective_value('interfaces openvpn {} local-port'.format(intf))
        if local_host and local_port:
            data['local'] = local_host + ':' + local_port

        if args.mode in ['client', 'site-to-site']:
            for client in data['clients']:
                if config.exists_effective('interfaces openvpn {} shared-secret-key-file'.format(intf)):
                    client['name'] = "None (PSK)"

                remote_host = config.return_effective_values('interfaces openvpn {} remote-host'.format(intf))
                remote_port = config.return_effective_value('interfaces openvpn {} remote-port'.format(intf))

                if not remote_port:
                    remote_port = '1194'

                if len(remote_host) >= 1:
                    client['remote'] = str(remote_host[0]) + ':' + remote_port

                client['tunnel'] = 'N/A'

        tmpl = jinja2.Template(outp_tmpl)
        print(tmpl.render(data))
