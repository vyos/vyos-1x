# configtree -- a standalone VyOS config file manipulation library (Python bindings)
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import re
import json
import logging

from ctypes import cdll, c_char_p, c_void_p, c_int, c_bool
from functools import lru_cache
from typing import TYPE_CHECKING
from pathlib import Path


# https://peps.python.org/pep-0484/#forward-references
# for type 'ConfigDict'
if TYPE_CHECKING:
    from vyos.referencetree import ReferenceTree

BUILD_PATH = '/tmp/libvyosconfig/_build/libvyosconfig.so'
INSTALL_PATH = '/usr/lib/libvyosconfig.so.0'
LIBPATH = BUILD_PATH if os.path.isfile(BUILD_PATH) else INSTALL_PATH

# C symbol -> (argtypes, restype). A restype of None means "leave the ctypes
# default (c_int)", which is what these entry points relied on before.
_PROTOTYPES = {
    'from_string': ([c_char_p], c_void_p),
    'get_error': ([], c_char_p),
    'to_string': ([c_void_p, c_bool], c_char_p),
    'to_commands': ([c_void_p, c_char_p], c_char_p),
    'read_internal': ([c_char_p], c_void_p),
    'write_internal': ([c_void_p, c_char_p], None),
    'read_internal_string': ([c_char_p], c_void_p),
    'write_internal_string': ([c_void_p], c_char_p),
    'to_json': ([c_void_p], c_char_p),
    'to_json_ast': ([c_void_p], c_char_p),
    'create_node': ([c_void_p, c_char_p], c_int),
    'set_add_value': ([c_void_p, c_char_p, c_char_p], c_int),
    'delete_value': ([c_void_p, c_char_p, c_char_p], c_int),
    'delete_node': ([c_void_p, c_char_p], c_int),
    'rename_node': ([c_void_p, c_char_p, c_char_p], c_int),
    'copy_node': ([c_void_p, c_char_p, c_char_p], c_int),
    'set_replace_value': ([c_void_p, c_char_p, c_char_p], c_int),
    'set_valueless': ([c_void_p, c_char_p], c_int),
    'exists': ([c_void_p, c_char_p], c_int),
    'value_exists': ([c_void_p, c_char_p, c_char_p], c_int),
    'list_nodes': ([c_void_p, c_char_p], c_char_p),
    'return_value': ([c_void_p, c_char_p], c_char_p),
    'return_values': ([c_void_p, c_char_p], c_char_p),
    'is_tag': ([c_void_p, c_char_p], c_int),
    'set_tag': ([c_void_p, c_char_p, c_bool], c_int),
    'is_leaf': ([c_void_p, c_char_p], c_bool),
    'set_leaf': ([c_void_p, c_char_p, c_bool], c_int),
    # third argument 'with_node' was passed unchecked before
    'get_subtree': ([c_void_p, c_char_p, c_bool], c_void_p),
    'destroy': ([c_void_p], None),
    'equal': ([c_void_p, c_void_p], c_bool),
    'config_dict': (
        [c_void_p, c_void_p, c_void_p, c_char_p, c_bool, c_bool],
        c_char_p,
    ),
    'diff_tree': ([c_char_p, c_void_p, c_void_p], c_void_p),
    'diff_compare': ([c_bool, c_char_p, c_void_p, c_void_p], c_char_p),
    'diff_show': ([c_void_p, c_void_p, c_void_p, c_char_p], c_char_p),
    'tree_union': ([c_void_p, c_void_p], c_void_p),
    'tree_merge': ([c_bool, c_void_p, c_void_p], c_void_p),
    'mask_inclusive': ([c_void_p, c_void_p], c_void_p),
    'mask_exclusive': ([c_void_p, c_void_p], c_void_p),
    'subtree_from_partial': ([c_void_p, c_void_p, c_void_p, c_char_p], c_void_p),
    'subtree_values_of_path': ([c_void_p, c_void_p, c_char_p], c_char_p),
    'reference_tree_to_json': ([c_char_p, c_char_p, c_char_p], None),
    'merge_reference_tree_cache': ([c_char_p, c_char_p, c_char_p], None),
    'interface_definitions_to_cache': ([c_char_p, c_char_p], None),
    'reference_tree_cache_to_json': ([c_char_p, c_char_p], None),
    # returns a tree pointer; without an explicit restype ctypes defaulted to
    # c_int and truncated it to 32 bits
    'validate_tree_filter': ([c_void_p, c_char_p, c_char_p], c_void_p),
    # vyos.referencetree
    'read_internal_string_reference_tree': ([c_char_p], c_void_p),
    'write_internal_reference_tree': ([c_void_p, c_char_p], None),
    'to_json_reference_tree': ([c_void_p], c_char_p),
    'get_owner': ([c_void_p, c_char_p], c_char_p),
    'get_multi_nodes': ([c_void_p, c_char_p], c_char_p),
    'get_tag_nodes': ([c_void_p, c_char_p], c_char_p),
    'get_nodes_of_kind': ([c_void_p, c_char_p, c_char_p], c_char_p),
    'get_rdeps_of_kind': ([c_void_p, c_char_p, c_char_p], c_char_p),
    'get_rdeps_of_kind_data': ([c_void_p, c_char_p, c_char_p], c_char_p),
}


class _Lib:
    """Lazily resolving, prototype-declaring wrapper around libvyosconfig.

    A symbol is looked up and given its argtypes/restype on first use, then
    cached as an instance attribute so __getattr__ is bypassed from then on.
    Resolution stays lazy on purpose: not every build of the library exports
    every entry point, and the previous per-instance binding code only failed
    on symbols that were actually used.
    """

    # pylint: disable=too-few-public-methods

    def __init__(self, libpath):
        self.__dict__['_lib'] = cdll.LoadLibrary(libpath)

    def __getattr__(self, name):
        try:
            argtypes, restype = _PROTOTYPES[name]
        except KeyError:
            raise AttributeError(
                f'{name} is not a known libvyosconfig entry point'
            ) from None
        func = getattr(self._lib, name)
        func.argtypes = argtypes
        if restype is not None:
            func.restype = restype
        setattr(self, name, func)
        return func


@lru_cache(maxsize=None)
def get_lib(libpath=LIBPATH):
    """Load libvyosconfig once per process.

    Every ConfigTree/DiffTree used to re-open the library and re-assign all
    argtypes/restypes in its constructor; the result is cached here instead.
    Loading stays lazy so that importing this module does not require the
    shared object to be present.
    """
    return _Lib(libpath)


def replace_backslash(s, search, replace):
    """Modify quoted strings containing backslashes not of escape sequences"""

    def replace_method(match):
        result = match.group().replace(search, replace)
        return result

    p = re.compile(r'("[^"]*[\\][^"]*"\n|\'[^\']*[\\][^\']*\'\n)')
    return p.sub(replace_method, s)


def escape_backslash(string: str) -> str:
    """Escape single backslashes in quoted strings"""
    result = replace_backslash(string, '\\', '\\\\')
    return result


def unescape_backslash(string: str) -> str:
    """Unescape backslashes in quoted strings"""
    result = replace_backslash(string, '\\\\', '\\')
    return result


def extract_version(s):
    """Extract the version string from the config string"""
    t = re.split('(^//)', s, maxsplit=1, flags=re.MULTILINE)
    return (t[0], ''.join(t[1:]))


def check_path(path):
    # Necessary type checking
    if not isinstance(path, list):
        raise TypeError(f'Expected a list, got a {type(path)}')


class ConfigTreeError(Exception):
    pass


class ConfigTree:
    # pylint: disable=too-many-instance-attributes,too-many-arguments,too-many-statements,too-many-public-methods,raise-missing-from
    def __init__(
        self,
        config_string=None,
        address=None,
        internal=None,
        internal_string=None,
        libpath=LIBPATH,
    ):
        args = [config_string, address, internal, internal_string]
        arg_names = ['config_string', 'address', 'internal', 'internal_string']
        if all(x is None for x in args):
            raise TypeError(
                "ConfigTree() requires one of 'config_string', 'address', 'internal', or 'internal_string'"
            )
        if sum(x is not None for x in args) > 1:
            raise TypeError(
                "ConfigTree() requires exactly one of 'config_string', 'address', 'internal', or 'internal_string'"
            )

        arg = [(k, v) for (k, v) in zip(arg_names, args) if v is not None][0]

        self.__config = None
        self.__lib = get_lib(libpath)

        match arg:
            case ('address', address):
                self.__config = address
                self.__version = ''
            case ('internal', internal):
                try:
                    cache_string = Path(internal).read_bytes()
                except OSError as e:
                    raise ValueError(f'Failed to read internal cache file: {e}')
                config = self.__lib.read_internal_string(cache_string)
                if config is None:
                    msg = self.__lib.get_error().decode()
                    raise ValueError(
                        f'Failed to read internal representation from file {internal}: {msg}'
                    )
                self.__config = config
                self.__version = ''
            case ('internal_string', internal_string):
                config = self.__lib.read_internal_string(internal_string.encode())
                if config is None:
                    msg = self.__lib.get_error().decode()
                    raise ValueError(
                        f'Failed to read internal representation from string: {msg}'
                    )
                self.__config = config
                self.__version = ''
            case ('config_string', config_string):
                config_section, version_section = extract_version(config_string)
                config_section = escape_backslash(config_section)
                config = self.__lib.from_string(config_section.encode())
                if config is None:
                    msg = self.__lib.get_error().decode()
                    raise ValueError(f'Failed to parse config: {msg}')
                self.__config = config
                self.__version = version_section
            case _:
                raise TypeError(
                    "ConfigTree() requires one of 'config_string', 'address', 'internal', or 'internal_string'"
                )

        self.__migration = os.environ.get('VYOS_MIGRATION')
        if self.__migration:
            self.migration_log = logging.getLogger('vyos.migrate')

    @classmethod
    def load_file(cls, location):
        # pylint: disable=raise-missing-from
        config_file = Path(location)
        if not config_file.exists():
            raise ConfigTreeError(f'Missing config file at {location}')
        try:
            config_tree = cls(config_file.read_text())
        except (OSError, ValueError, TypeError) as e:
            raise ConfigTreeError(f'Corrupted config file at {location}: {e}')

        return config_tree

    def __del__(self):
        if self.__config is not None:
            self.__lib.destroy(self.__config)

    def __eq__(self, other):
        if isinstance(other, ConfigTree):
            return self.__lib.equal(self.get_tree(), other.get_tree())
        return False

    def __str__(self):
        return self.to_string()

    def get_tree(self):
        return self.__config

    def get_version_string(self):
        return self.__version

    def write_cache(self, file_name):
        cache_string = self.__lib.write_internal_string(self.get_tree())
        try:
            Path(file_name).write_bytes(cache_string)
        except OSError as e:
            raise ValueError(f'Failed to write internal cache file: {e}')

    def write_internal_string(self) -> str:
        res = self.__lib.write_internal_string(self.get_tree())
        return res.decode()

    def to_string(self, ordered_values=False, no_version=False):
        config_string = self.__lib.to_string(self.__config, ordered_values).decode()
        config_string = unescape_backslash(config_string)
        if no_version:
            return config_string
        config_string = f'{config_string}\n{self.__version}'
        return config_string

    def to_commands(self, op='set'):
        commands = self.__lib.to_commands(self.__config, op.encode()).decode()
        commands = unescape_backslash(commands)
        return commands

    def to_json(self):
        return self.__lib.to_json(self.__config).decode()

    def to_json_ast(self):
        return self.__lib.to_json_ast(self.__config).decode()

    def create_node(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.create_node(self.__config, path_str)
        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(f'{msg}: {path}')

    def set(self, path, value=None, replace=True):
        """Set new entry in VyOS configuration.
        path: configuration path e.g. 'system dns forwarding listen-address'
        value: value to be added to node, e.g. '172.18.254.201'
        replace: True: current occurrence will be replaced
                 False: new value will be appended to current occurrences - use
                 this for adding values to a multi node
        """

        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        if value is None:
            res = self.__lib.set_valueless(self.__config, path_str)
        else:
            if replace:
                res = self.__lib.set_replace_value(
                    self.__config, path_str, str(value).encode()
                )
            else:
                res = self.__lib.set_add_value(
                    self.__config, path_str, str(value).encode()
                )

        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(
                f'{msg}: path "{path}" value "{value}" replace "{replace}"'
            )

        if self.__migration:
            self.migration_log.info(
                f'- op: set path: {path} value: {value} replace: {replace}'
            )

    def delete(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.delete_node(self.__config, path_str)
        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(f'{msg}: path "{path}"')

        if self.__migration:
            self.migration_log.info(f'- op: delete path: {path}')

    def delete_value(self, path, value):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.delete_value(self.__config, path_str, value.encode())
        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(f'{msg}: path "{path}" value "{value}"')

        if self.__migration:
            self.migration_log.info(f'- op: delete_value path: {path} value: {value}')

    def rename(self, path, new_name):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()
        newname_str = new_name.encode()

        # Check if a node with intended new name already exists
        new_path = path[:-1] + [new_name]
        if self.exists(new_path):
            raise ConfigTreeError(f'Name {new_name} already exists')

        res = self.__lib.rename_node(self.__config, path_str, newname_str)
        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(f'{msg}: {path}')

        if self.__migration:
            self.migration_log.info(
                f'- op: rename old_path: {path} new_path: {new_path}'
            )

    def copy(self, old_path, new_path):
        check_path(old_path)
        check_path(new_path)
        oldpath_str = ' '.join(map(str, old_path)).encode()
        newpath_str = ' '.join(map(str, new_path)).encode()

        # Check if a node with intended new name already exists
        if self.exists(new_path):
            raise ConfigTreeError()
        res = self.__lib.copy_node(self.__config, oldpath_str, newpath_str)
        if res != 0:
            msg = self.__lib.get_error().decode()
            raise ConfigTreeError(msg)

        if self.__migration:
            self.migration_log.info(
                f'- op: copy old_path: {old_path} new_path: {new_path}'
            )

    def exists(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.exists(self.__config, path_str)
        return bool(res)

    def value_exists(self, path, value):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.value_exists(self.__config, path_str, value.encode())
        return bool(res)

    def list_nodes(self, path, path_must_exist=True):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res_json = self.__lib.list_nodes(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            if path_must_exist:
                raise ConfigTreeError(f"Path {path} doesn't exist")
            return []
        return res

    def return_value(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res_json = self.__lib.return_value(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            raise ConfigTreeError(f"Path {path} doesn't exist")
        return res

    def return_values(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res_json = self.__lib.return_values(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            raise ConfigTreeError(f"Path {path} doesn't exist")
        return res

    def is_tag(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.is_tag(self.__config, path_str)
        return bool(res)

    def set_tag(self, path, value=True):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.set_tag(self.__config, path_str, value)
        if res == 0:
            return True
        msg = self.__lib.get_error().decode()
        raise ConfigTreeError(f'{msg}: {path}')

    def is_leaf(self, path):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.is_leaf(self.__config, path_str)
        return bool(res)

    def set_leaf(self, path, value):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.set_leaf(self.__config, path_str, value)
        if res == 0:
            return True
        msg = self.__lib.get_error().decode()
        raise ConfigTreeError(f'{msg}: {path}')

    def get_subtree(self, path, with_node=False):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.get_subtree(self.__config, path_str, with_node)
        subt = ConfigTree(address=res)
        return subt

    def config_dict(
        self, ref_tree, path, mask, get_first_key=False, with_defaults=False
    ):
        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res_json = self.__lib.config_dict(
            self.__config,
            ref_tree.get_tree(),
            mask.get_tree(),
            path_str,
            get_first_key,
            with_defaults,
        ).decode()
        res = json.loads(res_json)
        return res


def diff_compare(left, right, path=None, commands=False, libpath=LIBPATH):
    if left is None:
        left = ConfigTree(config_string='\n')
    if right is None:
        right = ConfigTree(config_string='\n')
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')
    path = path or []
    if path:
        if (not left.exists(path)) and (not right.exists(path)):
            raise ConfigTreeError(f"Path {path} doesn't exist")

    check_path(path)
    path_str = ' '.join(map(str, path)).encode()

    lib = get_lib(libpath)

    res = lib.diff_compare(commands, path_str, left.get_tree(), right.get_tree())
    res = res.decode()
    if res == '#1@':
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    res = unescape_backslash(res)
    return res


def diff_show(rt, left, right, path=None, libpath=LIBPATH):
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')
    path = path or []

    check_path(path)
    path_str = ' '.join(map(str, path)).encode()

    lib = get_lib(libpath)

    res = lib.diff_show(rt.get_tree(), left.get_tree(), right.get_tree(), path_str)
    res = res.decode()
    if res == '#1@':
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    res = unescape_backslash(res)
    return res


def union(left, right, libpath=LIBPATH):
    if left is None:
        left = ConfigTree(config_string='\n')
    if right is None:
        right = ConfigTree(config_string='\n')
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')

    lib = get_lib(libpath)

    res = lib.tree_union(left.get_tree(), right.get_tree())
    tree = ConfigTree(address=res)

    return tree


def merge(left, right, destructive=False, libpath=LIBPATH):
    if left is None:
        left = ConfigTree(config_string='\n')
    if right is None:
        right = ConfigTree(config_string='\n')
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')

    lib = get_lib(libpath)

    res = lib.tree_merge(destructive, left.get_tree(), right.get_tree())
    tree = ConfigTree(address=res)

    return tree


def mask_inclusive(left, right, libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')

    try:
        lib = get_lib(libpath)

        res = lib.mask_inclusive(left.get_tree(), right.get_tree())
    except Exception as e:
        raise ConfigTreeError(e)
    if not res:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    tree = ConfigTree(address=res)

    return tree


def mask_exclusive(left, right, libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
        raise TypeError('Arguments must be instances of ConfigTree')

    try:
        lib = get_lib(libpath)

        res = lib.mask_exclusive(left.get_tree(), right.get_tree())
    except Exception as e:
        raise ConfigTreeError(e)
    if not res:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    tree = ConfigTree(address=res)

    return tree


def delete_tree_from_masks(
    config_tree: ConfigTree, include_mask: ConfigTree, exclude_mask: ConfigTree
):
    masked_inc = mask_inclusive(config_tree, include_mask)
    # Here we want the reversed stand-alone exclusion/inclusion.
    # This simplifies definition of delete paths as (delete)
    # difference between the two trees of config data.
    masked_upper_bound = mask_exclusive(config_tree, include_mask)
    masked_lower_bound = mask_inclusive(config_tree, exclude_mask)
    masked_exc = union(masked_upper_bound, masked_lower_bound)

    ret = DiffTree(masked_inc, masked_exc)
    return ret.delete


def delete_dict_from_masks(
    config_tree: ConfigTree, include_mask: ConfigTree, exclude_mask: ConfigTree
):
    ret = delete_tree_from_masks(config_tree, include_mask, exclude_mask)
    return json.loads(ret.to_json())


def subtree_from_partial(
    config_tree: ConfigTree,
    path: list[str],
    reference_tree: 'ReferenceTree',
    start: ConfigTree = None,
    libpath=LIBPATH,
):
    # pylint: disable=raise-missing-from
    if start:
        if not isinstance(start, ConfigTree):
            raise TypeError("Argument 'start' must be an instance of ConfigTree")
    else:
        start = ConfigTree('')

    check_path(path)
    path_str = ' '.join(map(str, path)).encode()

    try:
        lib = get_lib(libpath)

        res = lib.subtree_from_partial(
            reference_tree.get_tree(),
            config_tree.get_tree(),
            start.get_tree(),
            path_str,
        )
    except Exception as e:
        raise ConfigTreeError(e)
    if not res:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    tree = ConfigTree(address=res)

    return tree


def subtree_values_of_path(
    config_tree: ConfigTree,
    path: list[str],
    reference_tree: 'ReferenceTree',
    libpath=LIBPATH,
) -> list[tuple[list[str], list[str]]]:
    # pylint: disable=raise-missing-from
    check_path(path)
    path_str = ' '.join(map(str, path)).encode()

    try:
        lib = get_lib(libpath)

        res = lib.subtree_values_of_path(
            reference_tree.get_tree(),
            config_tree.get_tree(),
            path_str,
        )
        res = res.decode()
    except Exception as e:
        raise ConfigTreeError(e)
    if res == '#1@':
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)

    lst = json.loads(res)
    return list(map(tuple, lst))


def reference_tree_to_json(from_dir, to_file, internal_cache='', libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    try:
        lib = get_lib(libpath)
        res = lib.reference_tree_to_json(
            internal_cache.encode(), from_dir.encode(), to_file.encode()
        )
    except Exception as e:
        raise ConfigTreeError(e)
    if res == 1:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)


def merge_reference_tree_cache(cache_dir, primary_name, result_name, libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    try:
        lib = get_lib(libpath)
        res = lib.merge_reference_tree_cache(
            cache_dir.encode(), primary_name.encode(), result_name.encode()
        )
    except Exception as e:
        raise ConfigTreeError(e)
    if res == 1:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)


def interface_definitions_to_cache(from_dir, cache_path, libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    try:
        lib = get_lib(libpath)
        res = lib.interface_definitions_to_cache(from_dir.encode(), cache_path.encode())
    except Exception as e:
        raise ConfigTreeError(e)
    if res == 1:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)


def reference_tree_cache_to_json(cache_path, render_file, libpath=LIBPATH):
    # pylint: disable=raise-missing-from
    try:
        lib = get_lib(libpath)
        res = lib.reference_tree_cache_to_json(
            cache_path.encode(), render_file.encode()
        )
    except Exception as e:
        raise ConfigTreeError(e)
    if res == 1:
        msg = lib.get_error().decode()
        raise ConfigTreeError(msg)


# validate_tree_filter c_ptr rt_cache validator_dir
def validate_tree_filter(
    config_tree,
    cache_path='/usr/share/vyos/reftree.cache',
    validator_dir='/usr/libexec/vyos/validators',
    libpath=LIBPATH,
):
    # pylint: disable=raise-missing-from
    try:
        lib = get_lib(libpath)
        res = lib.validate_tree_filter(
            config_tree.get_tree(), cache_path.encode(), validator_dir.encode()
        )
    except Exception as e:
        raise ConfigTreeError(e)

    msg = lib.get_error().decode()
    tree = ConfigTree(address=res)

    return tree, msg


def validate_tree(
    config_tree,
    cache_path='/usr/share/vyos/reftree.cache',
    validator_dir='/usr/libexec/vyos/validators',
):
    _, out = validate_tree_filter(
        config_tree, cache_path=cache_path, validator_dir=validator_dir
    )

    return out


class DiffTree:
    # pylint: disable=too-many-instance-attributes,too-few-public-methods
    def __init__(self, left, right, path=None, libpath=LIBPATH):
        if left is None:
            left = ConfigTree(config_string='\n')
        if right is None:
            right = ConfigTree(config_string='\n')
        if not (isinstance(left, ConfigTree) and isinstance(right, ConfigTree)):
            raise TypeError('Arguments must be instances of ConfigTree')
        path = path or []
        if path:
            if not left.exists(path):
                raise ConfigTreeError(f"Path {path} doesn't exist in lhs tree")
            if not right.exists(path):
                raise ConfigTreeError(f"Path {path} doesn't exist in rhs tree")

        self.left = left
        self.right = right

        self.__lib = get_lib(libpath)

        check_path(path)
        path_str = ' '.join(map(str, path)).encode()

        res = self.__lib.diff_tree(path_str, left.get_tree(), right.get_tree())

        # full diff config_tree and python dict representation
        self.full = ConfigTree(address=res)
        self.dict = json.loads(self.full.to_json())

        # config_tree sub-trees
        self.add = self.full.get_subtree(['add'])
        self.sub = self.full.get_subtree(['sub'])
        self.inter = self.full.get_subtree(['inter'])
        self.delete = self.full.get_subtree(['del'])

    def to_commands(self):
        add = self.add.to_commands()
        delete = self.delete.to_commands(op='delete')
        return delete + '\n' + add


def deep_copy(config_tree: ConfigTree) -> ConfigTree:
    """An inelegant, but reasonably fast, copy; replace with backend copy"""
    D = DiffTree(None, config_tree)
    return D.add
