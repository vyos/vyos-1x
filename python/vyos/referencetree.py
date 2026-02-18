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

from ctypes import cdll, c_char_p, c_void_p, c_bool

from vyos.defaults import reference_tree_cache

LIBPATH = '/usr/lib/libvyosconfig.so.0'


class ReferenceTreeError(Exception):
    pass


class ReferenceTree:
    # pylint: disable=too-many-instance-attributes
    def __init__(self, cache_file=reference_tree_cache, libpath=LIBPATH):
        self.__pointer = None
        self.__lib = cdll.LoadLibrary(libpath)

        # Import functions
        self.__get_error = self.__lib.get_error
        self.__get_error.argtypes = []
        self.__get_error.restype = c_char_p

        self.__read_internal = self.__lib.read_internal_reference_tree
        self.__read_internal.argtypes = [c_char_p]
        self.__read_internal.restype = c_void_p

        self.__write_internal = self.__lib.write_internal_reference_tree
        self.__write_internal.argtypes = [c_void_p, c_char_p]

        self.__to_json = self.__lib.to_json_reference_tree
        self.__to_json.argtypes = [c_void_p]
        self.__to_json.restype = c_char_p

        self.__destroy = self.__lib.destroy
        self.__destroy.argtypes = [c_void_p]

        self.__equal = self.__lib.equal
        self.__equal.argtypes = [c_void_p, c_void_p]
        self.__equal.restype = c_bool

        pointer = self.__read_internal(cache_file.encode())
        if pointer is None:
            msg = self.__get_error().decode()
            raise ValueError(f'Failed to read internal rep: {msg}')
        self.__pointer = pointer

    def __del__(self):
        if self.__pointer is not None:
            self.__destroy(self.__pointer)

    def __eq__(self, other):
        if isinstance(other, ReferenceTree):
            return self.__equal(self.get_tree(), other.get_tree())
        return False

    def __str__(self):
        return self.to_json()

    def get_tree(self):
        return self.__pointer

    def write_cache(self, file_name):
        self.__write_internal(self.get_tree(), file_name.encode())

    def to_json(self):
        return self.__to_json(self.__pointer).decode()
