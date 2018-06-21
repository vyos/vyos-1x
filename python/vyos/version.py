# Copyright 2017 VyOS maintainers and contributors <maintainers@vyos.io>
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
VyOS version data access library.

VyOS stores its version data, which include the version number and some
additional information in a JSON file. This module provides a convenient
interface to reading it.

Example of the version data dict::
  {
   'built_by': 'autobuild@vyos.net',
   'build_id': '021ac2ee-cd07-448b-9991-9c68d878cddd',
   'version': '1.2.0-rolling+201806200337',
   'built_on': 'Wed 20 Jun 2018 03:37 UTC'
  }
"""

import os
import json

import vyos.defaults

version_file = os.path.join(vyos.defaults.directories['data'], 'version.json')
  
def get_version_data(file=version_file):
    """
    Get complete version data

    Args:
        file (str): path to the version file

    Returns:
        dict: version data

    The optional ``file`` argument comes in handy in upgrade scripts
    that need to retrieve information from images other than the running image.
    It should not be used on a running system since the location of that file
    is an implementation detail and may change in the future, while the interface
    of this module will stay the same.
    """
    with open(file, 'r') as f:
        version_data = json.load(f)
    return version_data

def get_version(file=None):
    """
    Get the version number
    """
    version_data = None
    if file:
        version_data = get_version_data(file=file)
    else:
        version_data = get_version_data()
    return version_data["version"]
