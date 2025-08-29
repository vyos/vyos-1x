#!/usr/bin/env python3
#
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
import argparse
from vyos.vpp.utils import (
    get_hugepage_sizes,
    get_default_hugepage_size,
    get_default_page_size,
    bytes_to_human_memory,
)


def get_default_page_sizes() -> list[int]:
    """
    Retrieve the system's default page sizes, including huge pages.
    :return: A list of page sizes in bytes.
    """
    page_sizes = []
    # default system page size
    page_size = get_default_page_size()
    if page_size:
        page_sizes.append(page_size)

    # default huge page size
    page_size = get_default_hugepage_size()
    if page_size:
        page_sizes.append(page_size)

    return page_sizes


def list_mem_page_size(hugepage_only=None) -> list[str]:
    result = []
    page_sizes = get_hugepage_sizes()

    if not hugepage_only:
        page_sizes += get_default_page_sizes()

    page_sizes = set(page_sizes)
    for unit in ['K', 'M', 'G']:
        for size in page_sizes:
            if val := bytes_to_human_memory(size, unit):
                result.append(val)

    return result


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument(
        '--hugepage_only', type=str, help='List only available hugepage sizes.'
    )
    args = parser.parse_args()

    result = list_mem_page_size(args.hugepage_only)
    print(' '.join(result))
