#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import argparse

from vyos.config import Config
from vyos.tpm import tpm_enabled
from vyos.tpm_pki import get_tpm_list

def get_pki_certificates():
    config = Config()
    base = ['pki', 'certificate']
    conf = config.get_config_dict(base, key_mangling=('-', '_'))
    groups = []

    print(conf.get('certificate', []))
    for group in conf.get('certificate', []):
        groups.append(group)

    return groups

if __name__ == "__main__":
    groups = []
    if tpm_enabled():
        groups = get_tpm_list('cert')
    else:
        groups = get_pki_certificates()

    print(" ".join(groups))

if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--selector', help='Selector: csr|cert|kpair', required=True)
    args = parser.parse_args()
    final_list = []

    if tpm_enabled():
        final_list = get_tpm_list(args.selector)
    else:
        if args.selector =='cert':
            final_list = get_pki_certificates()

    if final_list:
        print(' '.join(final_list))
