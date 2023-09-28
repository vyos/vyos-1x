#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
#
#

import os
import sys
from argparse import ArgumentParser
from argparse import ArgumentTypeError

try:
    from vyos.configdep import check_dependency_graph
    from vyos.defaults import directories
except ImportError:
    # allow running during addon package build
    _here = os.path.dirname(__file__)
    sys.path.append(os.path.join(_here, '../../python/vyos'))
    from configdep import check_dependency_graph
    from defaults import directories

# addon packages will need to specify the dependency directory
dependency_dir = os.path.join(directories['data'],
                              'config-mode-dependencies')

def path_exists(s):
    if not os.path.exists(s):
        raise ArgumentTypeError("Must specify a valid vyos-1x dependency directory")
    return s

def main():
    parser = ArgumentParser(description='generate and save dict from xml defintions')
    parser.add_argument('--dependency-dir', type=path_exists,
                        default=dependency_dir,
                        help='location of vyos-1x dependency directory')
    parser.add_argument('--supplement', type=str,
                        help='supplemental dependency file')
    args = vars(parser.parse_args())

    if not check_dependency_graph(**args):
        sys.exit(1)

    sys.exit(0)

if __name__ == '__main__':
    main()
