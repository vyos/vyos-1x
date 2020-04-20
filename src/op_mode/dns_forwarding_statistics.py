#!/usr/bin/env python3

import jinja2
from sys import exit

from vyos.config import Config
from vyos.util import cmd

PDNS_CMD='/usr/bin/rec_control --socket-dir=/run/powerdns'

OUT_TMPL_SRC = """
DNS forwarding statistics:

Cache entries: {{ cache_entries -}}
Cache size: {{ cache_size }} kbytes

"""

if __name__ == '__main__':
    # Do nothing if service is not configured
    c = Config()
    if not c.exists_effective('service dns forwarding'):
        print("DNS forwarding is not configured")
        exit(0)

    data = {}

    data['cache_entries'] = cmd(f'{PDNS_CMD} get cache-entries')
    data['cache_size'] = "{0:.2f}".format( int(cmd(f'{PDNS_CMD} get cache-bytes')) / 1024 )

    tmpl = jinja2.Template(OUT_TMPL_SRC)
    print(tmpl.render(data))
