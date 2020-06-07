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
import logging

import vyos.defaults

from vyos.util import read_file
from vyos.util import read_json
from vyos.util import popen
from vyos.util import run
from vyos.util import DEVNULL


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

    cpu_json,code = popen('lscpu -J',stderr=DEVNULL)

    cpu = {}
    if code == 0:
        cpu_info = json.loads(cpu_json)
        if len(cpu_info) > 0 and 'lscpu' in cpu_info:
            for prop in cpu_info['lscpu']:
                if (prop['field'].find('Thread(s)') > -1): cpu['threads'] = prop['data'] 
                if (prop['field'].find('Core(s)')) > -1: cpu['cores'] = prop['data'] 
                if (prop['field'].find('Socket(s)')) > -1: cpu['sockets'] = prop['data'] 
                if (prop['field'].find('CPU(s):')) > -1: cpu['cpus'] = prop['data'] 
                if (prop['field'].find('CPU MHz')) > -1: cpu['mhz'] = prop['data'] 
                if (prop['field'].find('CPU min MHz')) > -1: cpu['mhz_min'] = prop['data'] 
                if (prop['field'].find('CPU max MHz')) > -1: cpu['mhz_max'] = prop['data'] 
                if (prop['field'].find('Vendor ID')) > -1: cpu['vendor'] = prop['data'] 
                if (prop['field'].find('Model name')) > -1: cpu['model'] = prop['data'] 

    if len(cpu) > 0:
        version_data['cpu'] = cpu



    hypervisor,code = popen('hvinfo', stderr=DEVNULL)
    if code == 1:
         # hvinfo returns 1 if it cannot detect any hypervisor
         version_data['system_type'] = 'bare metal'
    else:
        version_data['system_type'] = f"{hypervisor} guest"

    # Get boot type, it can be livecd, installed image, or, possible, a system installed
    # via legacy "install system" mechanism
    # In installed images, the squashfs image file is named after its image version,
    # while on livecd it's just "filesystem.squashfs", that's how we tell a livecd boot
    # from an installed image
    boot_via = "installed image"
    if run(""" grep -e '^overlay.*/filesystem.squashfs' /proc/mounts >/dev/null""") == 0:
        boot_via = "livecd"
    elif run(""" grep '^overlay /' /proc/mounts >/dev/null """) != 0:
        boot_via = "legacy non-image installation"
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
