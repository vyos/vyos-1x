#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from json import loads as json_loads, dumps as json_dumps
from pathlib import Path
from typing import Any

STORAGE_LOCATION = '/run/vpp'


class JSONStorage:
    def __init__(self, name: str = '') -> None:
        """Initiate a file storage

        Args:
            name (str, optional): Unique storage name. Defaults to '' (generate a name).

        Raises:
            err: In case a file for storage cannot be created
        """
        # If a name is not provided, this is a temporary one-time storage
        # this use case is strange, but let's allow this
        if not name:
            self.__temporary = True
            self.__cache: dict[Any, Any] = {}
            self.__locked = False
            return
        self.__temporary = False

        self.__storage = Path(f'{STORAGE_LOCATION}/{name}.json')
        self.__lock_file = Path(f'{STORAGE_LOCATION}/{name}.lock')

        # prepare a folder
        storage_dir = Path(STORAGE_LOCATION)
        if not storage_dir.exists():
            storage_dir.mkdir(parents=True)

        # initialize lock status
        self.__locked = False
        if self.__storage_locked():
            raise FileExistsError(f'Cannot open locked storage: {self.__storage}')
        self.__lock_file.touch()

        if not self.__storage.exists():
            try:
                self.__storage.touch()
            except Exception as err:
                print(f'Unable to initiate storage: {err}')
                raise err
            # prepare an empty cache
            self.__cache: dict[Any, Any] = {}
        else:
            # load a cache from file
            self.__cache = self.__load_file()

    def __del__(self) -> None:
        """Dump data to persistent storage and unlock it"""
        if self.__temporary:
            return
        # dump a cache to storage
        if self.__cache:
            self.__dump_file()
        # or remove a file
        else:
            self.__storage.unlink()
        # unlock a storage
        self.__lock_file.unlink()

    def __check_types(self, data: Any) -> None:
        """Check if all the data have supported types

        Args:
            data (Any): object to validate

        Raises:
            TypeError: If a data type is not supported
        """
        if isinstance(data, str | int | float | bool | None):
            return
        if isinstance(data, list):
            for item in data:
                self.__check_types(item)
            return
        if isinstance(data, dict):
            for item in data.values():
                self.__check_types(item)
            return
        raise TypeError(f'Object type "{type(data)}" is not allowed')

    def __load_file(self) -> dict[Any, Any]:
        """Read a file to a dictionary

        Returns:
            dict[Any, Any]: loaded dict object
        """
        data: bytes = self.__storage.read_bytes()
        return json_loads(data)

    def __dump_file(self) -> None:
        """Dump cache to a file"""
        data: str = json_dumps(self.__cache)
        self.__storage.write_text(data)

    def __lock(self) -> None:
        """Lock storage

        Raises:
            FileExistsError: Raised if a storage is already locked
        """
        if self.__locked:
            raise FileExistsError(f'Access is already locked: {self.__storage}')
        self.__locked = True

    def __unlock(self) -> None:
        """Unlock storage

        Raises:
            FileNotFoundError: Raised if a storage is already unlocked
        """
        if not self.__locked:
            raise FileNotFoundError(f'Access is already unlocked: {self.__storage}')
        self.__locked = False

    def __storage_locked(self) -> bool:
        """Check if a storage is locked

        Returns:
            bool: Lock status
        """
        if self.__lock_file.exists():
            return True
        return False

    def delete(self, key: Any = None) -> None:
        """Delete data from a storage or a full storage

        Raises:
            FileExistsError: Raised if a storage is locked
        """
        if self.__locked:
            raise FileExistsError(
                f'Storage locked and delete operation cannot be performed: {self.__storage}'
            )
        if key:
            if key not in self.__cache:
                raise ValueError(
                    f'Object {key} does not exist in storage {self.__storage}'
                )
            del self.__cache[key]
        else:
            self.__cache = {}

    def write(self, key: Any, value: Any) -> None:
        # Check types first
        self.__check_types(key)
        self.__check_types(value)
        # check lock status
        if self.__locked:
            raise FileExistsError(
                f'Storage is locked and cannot be written: {self.__storage}'
            )
        # write a data to a cache
        self.__lock()
        self.__cache[key] = value
        self.__unlock()

    def read(self, key: Any, default: Any = None) -> Any:
        """Read data from a storage

        Args:
            key (Any): key name
            default (Any, optional): Value to return if a key does not exist. Defaults to None.

        Raises:
            FileExistsError: Raised if a storage is locked

        Returns:
            Any: Value to return
        """
        # Check types first
        self.__check_types(key)
        # check lock status
        if self.__locked:
            raise FileExistsError(
                f'Storage is locked and it is not safe to read: {self.__storage}'
            )
        # read a data from cache
        self.__lock()
        data: Any | None = self.__cache.get(key, default)
        self.__unlock()

        return data
