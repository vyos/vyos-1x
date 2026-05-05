# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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


from vyos.configtree import ConfigTree


# pylint: disable=anomalous-backslash-in-string,pointless-string-statement
"""Activation scripts must be named '^\\d+\\-.+.py$' to be included by the
activation script runner. They are run in ascending order of prefix."""


def pre_condition() -> bool:
    """This function is not required.
    If not present, or pre_condition returns True, the function activate
    will be called on the config."""


def activate(_config: ConfigTree) -> None:
    """This function is expected.
    If not present, the script is ignored. The function itself can be a
    no-op."""


def post_condition() -> None:
    """This function is not required.
    If present, and application of 'activate' succeeds, post_condition will
    be called.
    Commonly used to set activation 'off' for the script, after first run on
    an installed system."""
