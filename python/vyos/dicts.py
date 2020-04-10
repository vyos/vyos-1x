#!/usr/bin/env python3
#
# Copyright (C) 2019 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


class FixedDict(dict):
    """
    FixedDict: A dictionnary not allowing new keys to be created after initialisation.

    >>> f = FixedDict(**{'count':1})
    >>> f['count'] = 2
    >>> f['king'] = 3
      File "...", line ..., in __setitem__
    raise ConfigError(f'Option "{k}" has no defined default')
    """

    def __init__(self, **options):
        self._allowed = options.keys()
        super().__init__(**options)

    def __setitem__(self, k, v):
        """
        __setitem__ is a builtin which is called by python when setting dict values:
        >>> d = dict()
        >>> d['key'] = 'value'
        >>> d
        {'key': 'value'}

        is syntaxic sugar for

        >>> d = dict()
        >>> d.__setitem__('key','value')
        >>> d
        {'key': 'value'}
        """
        if k not in self._allowed:
            raise ConfigError(f'Option "{k}" has no defined default')
        super().__setitem__(k, v)
