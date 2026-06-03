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
# You should have received a copy of the GNU Lesser General Public License
# along with this library.  If not, see <http://www.gnu.org/licenses/>.


from vyos.referencetree import ReferenceTree
from vyos.configtree import ConfigTree
from vyos.configtree import ConfigTreeError
from vyos.configtree import subtree_from_partial


class DerivedTreeError(Exception):
    """Error to be raised by functions of derivedtree"""


def subtree_from_list_of_partial_paths(
    ctree: ConfigTree, paths: list[list[str]], accumulator: ConfigTree = None
):
    """Return the union of subtrees of the ConfigTree argument matching each
    of the 'partial' paths. A partial path is one that may or may not
    contain intervening tag node values, in which case it will match for all
    values that apply.

    An existing subtree may be passed as the initial value of accumulator.
    """
    if accumulator:
        if not isinstance(accumulator, ConfigTree):
            raise TypeError("Argument 'accumulator' must be an instance of ConfigTree")
    else:
        accumulator = ConfigTree('')

    rtree = ReferenceTree()

    errors = []
    for path in paths:
        try:
            accumulator = subtree_from_partial(ctree, path, rtree, accumulator)
        except ConfigTreeError as e:
            errors.append(str(e))
            continue

    if errors:
        raise DerivedTreeError(f'Nonsensical paths: {errors}')

    return accumulator
