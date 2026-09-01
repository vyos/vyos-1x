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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

import importlib

__all__ = [
    'assertion',
    'auth',
    'boot',
    'commit',
    'configfs',
    'convert',
    'cpu',
    'dict',
    'file',
    'io',
    'kernel',
    'list',
    'locking',
    'misc',
    'network',
    'permission',
    'process',
    'system',
]


def __getattr__(name):
    """Import submodules on first access (PEP 562).

    Importing them eagerly pulled the whole set into every consumer of
    'from vyos.utils.<sub> import <name>', which is a measurable cost on the
    conf-mode script path where each script is a fresh interpreter.
    """
    if name not in __all__:
        raise AttributeError(f'module {__name__!r} has no attribute {name!r}')
    mod = importlib.import_module(f'{__name__}.{name}')
    globals()[name] = mod
    return mod


def __dir__():
    return sorted(list(globals()) + __all__)
