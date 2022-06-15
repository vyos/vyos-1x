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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import time

from vyos.configquery import ConfigTreeQuery
from vyos.firewall import get_ips_domains_dict
from vyos.firewall import nft_add_set_elements
from vyos.firewall import nft_flush_set
from vyos.firewall import nft_init_set
from vyos.firewall import nft_update_set_elements
from vyos.util import call


base = ['firewall', 'group', 'domain-group']
check_required = True
# count_failed = 0
# Timeout in sec between checks
timeout = 300

domain_state = {}

if __name__ == '__main__':

    while check_required:
        config = ConfigTreeQuery()
        if config.exists(base):
            domain_groups = config.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True)
            for set_name, domain_config in domain_groups.items():
                list_domains = domain_config['address']
                elements = []
                ip_dict = get_ips_domains_dict(list_domains)

                for domain in list_domains:
                    # Resolution succeeded, update domain state
                    if domain in ip_dict:
                        domain_state[domain] = ip_dict[domain]
                        elements += ip_dict[domain]
                    # Resolution failed, use previous domain state
                    elif domain in domain_state:
                        elements += domain_state[domain]

                # Resolve successful
                if elements:
                    nft_update_set_elements(f'D_{set_name}', elements)
        time.sleep(timeout)
