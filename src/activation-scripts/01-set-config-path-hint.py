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


from vyos.configtree import ConfigTree
from vyos.system.image import is_live_boot
from vyos.utils.activate import set_activation
from vyos.utils.activate import set_config_path_hint
from vyos.utils.activate import is_first_installed_boot


def pre_condition() -> bool:
    return not is_live_boot()


def activate(_config: ConfigTree) -> None:
    pass


def post_condition() -> None:
    if is_first_installed_boot():
        set_config_path_hint()
        set_activation(__file__, 'never')
