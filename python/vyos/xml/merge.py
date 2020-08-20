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

import sys

from xml.etree import ElementTree
from xml.dom import minidom

from vyos.xml.files import listing
from vyos.xml.files import include

# based on:
# https://bugs.python.org/issue27899
# but we do not want to change '/&apos;

def with_patched_elementree(function):
    def _escape_cdata(text):
        try:
            return text \
                .replace("&", "&amp;") \
                .replace("<", "&lt;") \
                .replace(">", "&gt;")
        except (TypeError, AttributeError):
            from xml.etree.ElementTree import _raise_serialization_error
            _raise_serialization_error(text)

    def inner(folder):
        escape_cdata = ElementTree._escape_cdata
        try:
            ElementTree._escape_cdata = _escape_cdata
            return function(folder)
        finally:
            ElementTree._escape_cdata = escape_cdata

    return inner


@with_patched_elementree
def from_folder(folder):
    tree = ElementTree.fromstring(
        '<?xml version="1.0"?>'
        '<interfaceDefinition>'
        '</interfaceDefinition>'
    )

    for fname in listing(folder):
        try:
            data = ElementTree.fromstring(include(fname))
            for result in data.iter('interfaceDefinition'):
                tree.extend(result)
                # merge(tree, data)
        except Exception:
            print(f'issue when parsing {fname}')
            import traceback
            traceback.print_exc()
            sys.exit(1)

    if not tree:
        return ''

    merged = ElementTree.tostring(tree)
    xmldom = minidom.parseString(merged)
    pretty = xmldom.toprettyxml(indent='  ', newl='\n')

    return '\n'.join(_ for _ in pretty.split('\n') if _.strip())
