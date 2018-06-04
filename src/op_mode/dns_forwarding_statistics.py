#!/usr/bin/env python3

import subprocess
import jinja2

from vyos.config import Config

PDNS_CMD='/usr/bin/rec_control'

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
        sys.exit(0)

    data = {}

    data['cache_entries'] = subprocess.check_output([PDNS_CMD, 'get cache-entries']).decode()
    data['cache_size'] = "{0:.2f}".format( int(subprocess.check_output([PDNS_CMD, 'get cache-bytes']).decode()) / 1024 )

    tmpl = jinja2.Template(OUT_TMPL_SRC)
    print(tmpl.render(data))
