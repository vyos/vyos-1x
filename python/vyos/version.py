# Copyright 2017-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import requests
import vyos.defaults
from vyos.system.image import is_live_boot

from vyos.utils.file import read_file
from vyos.utils.file import read_json
from vyos.utils.process import popen
from vyos.utils.process import DEVNULL

version_file = os.path.join(vyos.defaults.directories['data'], 'version.json')

def get_version_data(fname=version_file):
    """
    Get complete version data

    Args:
        file (str): path to the version file

    Returns:
        dict: version data, if it can not be found and empty dict

    The optional ``file`` argument comes in handy in upgrade scripts
    that need to retrieve information from images other than the running image.
    It should not be used on a running system since the location of that file
    is an implementation detail and may change in the future, while the interface
    of this module will stay the same.
    """
    return read_json(fname, {})


def get_version(fname=version_file):
    """
    Get the version number, or an empty string if it could not be determined
    """
    return get_version_data(fname=fname).get('version', '')


def get_full_version_data(fname=version_file):
    version_data = get_version_data(fname)

    # Get system architecture (well, kernel architecture rather)
    version_data['system_arch'], _ = popen('uname -m', stderr=DEVNULL)

    hypervisor,code = popen('hvinfo', stderr=DEVNULL)
    if code == 1:
         # hvinfo returns 1 if it cannot detect any hypervisor
         version_data['system_type'] = 'bare metal'
    else:
        version_data['system_type'] = f"{hypervisor} guest"

    # Get boot type, it can be livecd or installed image
    # In installed images, the squashfs image file is named after its image version,
    # while on livecd it's just "filesystem.squashfs", that's how we tell a livecd boot
    # from an installed image
    if is_live_boot():
        boot_via = "livecd"
    else:
        boot_via = "installed image"
    version_data['boot_via'] = boot_via

    # Get hardware details from DMI
    dmi = '/sys/class/dmi/id'
    version_data['hardware_vendor'] = read_file(dmi + '/sys_vendor', 'Unknown')
    version_data['hardware_model'] = read_file(dmi +'/product_name','Unknown')

    # These two assume script is run as root, normal users can't access those files
    subsystem = '/sys/class/dmi/id/subsystem/id'
    version_data['hardware_serial'] = read_file(subsystem + '/product_serial','Unknown')
    version_data['hardware_uuid'] = read_file(subsystem + '/product_uuid', 'Unknown')

    return version_data

def get_remote_version(url):
    """
    Get remote available JSON file from remote URL
    An example of the image-version.json

    [
       {
          "arch":"amd64",
          "flavors":[
           "generic"
        ],
        "image":"vyos-rolling-latest.iso",
        "latest":true,
        "lts":false,
        "release_date":"2022-09-06",
        "release_train":"sagitta",
        "url":"http://xxx/rolling/current/vyos-rolling-latest.iso",
        "version":"vyos-1.4-rolling-202209060217"
      }
    ]
    """
    headers = {}
    try:
        remote_data = requests.get(url=url, headers=headers)
        remote_data.raise_for_status()
        if remote_data.status_code != 200:
            return False
        return remote_data.json()
    except requests.exceptions.HTTPError as errh:
        print ("HTTP Error:", errh)
    except requests.exceptions.ConnectionError as errc:
        print ("Connecting error:", errc)
    except requests.exceptions.Timeout as errt:
        print ("Timeout error:", errt)
    except requests.exceptions.RequestException as err:
        print ("Unable to get remote data", err)
    return False
