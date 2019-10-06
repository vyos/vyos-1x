#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
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

import os
import jinja2

from copy import deepcopy
from sys import exit

from vyos.config import Config
from vyos import ConfigError

config_80211_file='/etc/modprobe.d/cfg80211.conf'
config_crda_file='/etc/default/crda'

# Please be careful if you edit the template.
config_80211_tmpl = """
{%- if regdom -%}
options cfg80211 ieee80211_regdom={{ regdom }}
{% endif %}
"""

# Please be careful if you edit the template.
config_crda_tmpl = """
{%- if regdom -%}
REGDOMAIN={{ regdom }}
{% endif %}
"""

default_config_data = {
    'regdom' : '',
    'deleted' : False
}


def get_config():
    regdom = deepcopy(default_config_data)
    conf = Config()

    # set new configuration level
    conf.set_level('system')

    # Check if interface has been removed
    if not conf.exists('wifi-regulatory-domain'):
        regdom['deleted'] = True
        return regdom

    # retrieve configured regulatory domain
    if conf.exists('wifi-regulatory-domain'):
        regdom['regdom'] = conf.return_value('wifi-regulatory-domain')

    return regdom

def verify(regdom):
    if regdom['deleted']:
        return None

    if not regdom['regdom']:
        raise ConfigError("Wireless regulatory domain is mandatory.")

    return None

def generate(regdom):
    print("Changing the wireless regulatory domain requires a system reboot.")

    if regdom['deleted']:
        if os.path.isfile(config_80211_file):
            os.unlink(config_80211_file)

        if os.path.isfile(config_crda_file):
            os.unlink(config_crda_file)

        return None

    tmpl = jinja2.Template(config_80211_tmpl)
    config_text = tmpl.render(regdom)
    with open(config_80211_file, 'w') as f:
        f.write(config_text)

    tmpl = jinja2.Template(config_crda_tmpl)
    config_text = tmpl.render(regdom)
    with open(config_crda_file, 'w') as f:
        f.write(config_text)

    return None

def apply(regdom):
    return None

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
