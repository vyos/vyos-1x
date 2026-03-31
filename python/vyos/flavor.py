# Copyright (C) VyOS Inc.
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

"""
VyOS flavor data access library.

VyOS stores its flavor specific data in a JSON file. This module provides a
convenient interface to reading it.

Example of the version data dict::
  {
   'console_type': 'ttyS0',
   'console_speed': '115200'
  }
"""

import os
import vyos.defaults

from vyos.utils.file import read_json

flavor_file = os.path.join(vyos.defaults.directories['data'], 'flavor.json')

def get_flavor_data(fname=flavor_file):
    """
    Get complete flavor data

    Args:
        file (str): path to the flavor file

    Returns:
        dict: flavor data, if it can not be found and empty dict

    The optional ``file`` argument comes in handy in upgrade scripts
    that need to retrieve information from images other than the running image.
    It should not be used on a running system since the location of that file
    is an implementation detail and may change in the future, while the interface
    of this module will stay the same.
    """
    return read_json(flavor_file, {})

def get_image_serial_console(fname=flavor_file):
    """
    Get serial console parameters baked into the image flavor.

    Args:
        file (str): path to the flavor file

    Returns:
        dict: serial interface data baked into the image flavor. Example:
          {"console_type": "ttyS", "console_speed": "115200", "console_num":"0"}
    """
    console_type = get_flavor_data(fname=fname).get('console_type', '')
    console_num = get_flavor_data(fname=fname).get('console_num', '')
    console_speed = get_flavor_data(fname=fname).get('console_speed', '')
    return (console_type, console_num, console_speed)
