# Copyright (C) 2020 VyOS maintainers and contributors
#
# This library is free software; you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation;
# either version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this library;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA

import glob

from os.path import join
from os.path import dirname


def listing(folder):
    """
    return all the xml and xml.in files in a folder
    """

    # the naming between operational and configuration
    # for the extension should be harmonised, to only
    # have .xml for the one to search

    for file in glob.glob(f'{folder}/*.xml'):
        yield file
    for file in glob.glob(f'{folder}/*.xml.in'):
        yield file


def include(fname, folder=''):
    """
    return the content of a file, including any file referenced with a #include
    """
    if not folder:
        folder = dirname(fname)
    content = ''
    with open(fname, 'r') as r:
        for line in r.readlines():
            if '#include' in line:
                content += include(join(folder, line.strip()[10:-1]), folder)
                continue
            content += line
    return content
