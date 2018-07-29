#!/usr/bin/env python3

import jinja2
import sys
import time

from vyos.config import Config

cache_file = r'/var/cache/ddclient/ddclient.cache'

OUT_TMPL_SRC = """
{%- for entry in hosts -%}
ip address   : {{ entry.ip }}
host-name    : {{ entry.host }}
last update  : {{ entry.time }}
update-status: {{ entry.status }}

{% endfor -%}
"""

if __name__ == '__main__':
    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service dns dynamic'):
        print("Dynamic DNS not configured")
        sys.exit(0)

    data = {
        'hosts': []
    }

    with open(cache_file, 'r') as f:
        for line in f:
            if line.startswith('#'):
                continue

            outp = {
                'host': '',
                'ip': '',
                'time': ''
            }

            if 'host=' in line:
                host = line.split('host=')[1]
                if host:
                    outp['host'] = host.split(',')[0]

            if 'ip=' in line:
                ip = line.split('ip=')[1]
                if ip:
                    outp['ip'] = ip.split(',')[0]

            if 'atime=' in line:
                atime = line.split('atime=')[1]
                if atime:
                    tmp = atime.split(',')[0]
                    outp['time'] = time.strftime("%Y-%m-%d %H:%M:%S", time.gmtime(int(tmp, base=10)))

            if 'status=' in line:
                status = line.split('status=')[1]
                if status:
                    outp['status'] = status.split(',')[0]

            data['hosts'].append(outp)

    tmpl = jinja2.Template(OUT_TMPL_SRC)
    print(tmpl.render(data))
