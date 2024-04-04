# Copyright 2020-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from enum import IntFlag
from enum import auto

from vyos.config import Config
from vyos.configtree import DiffTree
from vyos.configdict import dict_merge
from vyos.utils.dict import get_sub_dict
from vyos.utils.dict import mangle_dict_keys
from vyos.utils.dict import dict_search_args
from vyos.xml_ref import get_defaults

class ConfigDiffError(Exception):
    """
    Raised on config dict access errors, for example, calling get_value on
    a non-leaf node.
    """
    pass

def enum_to_key(e):
    return e.name.lower()

class Diff(IntFlag):
    MERGE = auto()
    DELETE = auto()
    ADD = auto()
    STABLE = auto()

ALL = Diff.MERGE | Diff.DELETE | Diff.ADD | Diff.STABLE

requires_effective = [enum_to_key(Diff.DELETE)]
target_defaults = [enum_to_key(Diff.MERGE)]

def _key_sets_from_dicts(session_dict, effective_dict):
    session_keys = list(session_dict)
    effective_keys = list(effective_dict)

    ret = {}
    stable_keys = [k for k in session_keys if k in effective_keys]

    ret[enum_to_key(Diff.MERGE)] = session_keys
    ret[enum_to_key(Diff.DELETE)] = [k for k in effective_keys if k not in stable_keys]
    ret[enum_to_key(Diff.ADD)] = [k for k in session_keys if k not in stable_keys]
    ret[enum_to_key(Diff.STABLE)] = stable_keys

    return ret

def _dict_from_key_set(key_set, d):
    # This will always be applied to a key_set obtained from a get_sub_dict,
    # hence there is no possibility of KeyError, as get_sub_dict guarantees
    # a return type of dict
    ret = {k: d[k] for k in key_set}

    return ret

def get_config_diff(config, key_mangling=None):
    """
    Check type and return ConfigDiff instance.
    """
    if not config or not isinstance(config, Config):
        raise TypeError("argument must me a Config instance")
    if key_mangling and not (isinstance(key_mangling, tuple) and \
            (len(key_mangling) == 2) and \
            isinstance(key_mangling[0], str) and \
            isinstance(key_mangling[1], str)):
        raise ValueError("key_mangling must be a tuple of two strings")

    if hasattr(config, 'cached_diff_tree'):
        diff_t = getattr(config, 'cached_diff_tree')
    else:
        diff_t = DiffTree(config._running_config, config._session_config)
        setattr(config, 'cached_diff_tree', diff_t)

    if hasattr(config, 'cached_diff_dict'):
        diff_d = getattr(config, 'cached_diff_dict')
    else:
        diff_d = diff_t.dict
        setattr(config, 'cached_diff_dict', diff_d)

    return ConfigDiff(config, key_mangling, diff_tree=diff_t,
                                            diff_dict=diff_d)

class ConfigDiff(object):
    """
    The class of config changes as represented by comparison between the
    session config dict and the effective config dict.
    """
    def __init__(self, config, key_mangling=None, diff_tree=None, diff_dict=None):
        self._level = config.get_level()
        self._session_config_dict = config.get_cached_root_dict(effective=False)
        self._effective_config_dict = config.get_cached_root_dict(effective=True)
        self._key_mangling = key_mangling

        self._diff_tree = diff_tree
        self._diff_dict = diff_dict

    # mirrored from Config; allow path arguments relative to level
    def _make_path(self, path):
        if isinstance(path, str):
            path = path.split()
        elif isinstance(path, list):
            pass
        else:
            raise TypeError("Path must be a whitespace-separated string or a list")

        ret = self._level + path
        return ret

    def set_level(self, path):
        """
        Set the *edit level*, that is, a relative config dict path.
        Once set, all operations will be relative to this path,
        for example, after ``set_level("system")``, calling
        ``get_value("name-server")`` is equivalent to calling
        ``get_value("system name-server")`` without ``set_level``.

        Args:
            path (str|list): relative config path
        """
        if isinstance(path, str):
            if path:
                self._level = path.split()
            else:
                self._level = []
        elif isinstance(path, list):
            self._level = path.copy()
        else:
            raise TypeError("Level path must be either a whitespace-separated string or a list")

    def get_level(self):
        """
        Gets the current edit level.

        Returns:
            str: current edit level
        """
        ret = self._level.copy()
        return ret

    def _mangle_dict_keys(self, config_dict):
        config_dict = mangle_dict_keys(config_dict, self._key_mangling[0],
                                                    self._key_mangling[1])
        return config_dict

    def is_node_changed(self, path=[]):
        if self._diff_tree is None:
            raise NotImplementedError("diff_tree class not available")

        if (self._diff_tree.add.exists(self._make_path(path)) or
            self._diff_tree.sub.exists(self._make_path(path))):
            return True
        return False

    def node_changed_presence(self, path=[]) -> bool:
        if self._diff_tree is None:
            raise NotImplementedError("diff_tree class not available")

        path = self._make_path(path)
        before = self._diff_tree.left.exists(path)
        after = self._diff_tree.right.exists(path)
        return (before and not after) or (not before and after)

    def node_changed_children(self, path=[]) -> list:
        if self._diff_tree is None:
            raise NotImplementedError("diff_tree class not available")

        path = self._make_path(path)
        add = self._diff_tree.add
        sub = self._diff_tree.sub
        children = set()
        if add.exists(path):
            children.update(add.list_nodes(path))
        if sub.exists(path):
            children.update(sub.list_nodes(path))

        return list(children)

    def get_child_nodes_diff_str(self, path=[]):
        ret = {'add': {}, 'change': {}, 'delete': {}}

        diff = self.get_child_nodes_diff(path,
                                expand_nodes=Diff.ADD | Diff.DELETE | Diff.MERGE | Diff.STABLE,
                                no_defaults=True)

        def parse_dict(diff_dict, diff_type, prefix=[]):
            for k, v in diff_dict.items():
                if isinstance(v, dict):
                    parse_dict(v, diff_type, prefix + [k])
                else:
                    path_str = ' '.join(prefix + [k])
                    if diff_type == 'add' or diff_type == 'delete':
                        if isinstance(v, list):
                            v = ', '.join(v)
                        ret[diff_type][path_str] = v
                    elif diff_type == 'merge':
                        old_value = dict_search_args(diff['stable'], *prefix, k)
                        if old_value and old_value != v:
                            ret['change'][path_str] = [old_value, v]

        parse_dict(diff['merge'], 'merge')
        parse_dict(diff['add'], 'add')
        parse_dict(diff['delete'], 'delete')

        return ret

    def get_child_nodes_diff(self, path=[], expand_nodes=Diff(0), no_defaults=False,
                             recursive=False):
        """
        Args:
            path (str|list): config path
            expand_nodes=Diff(0): bit mask of enum indicating for which nodes
                                  to provide full dict; for example, Diff.MERGE
                                  will expand dict['merge'] into dict under
                                  value
            no_detaults=False: if expand_nodes & Diff.MERGE, do not merge default
                               values to ret['merge']
            recursive: if true, use config_tree diff algorithm provided by
                       diff_tree class

        Returns: dict of lists, representing differences between session
                                and effective config, under path
                 dict['merge']  = session config values
                 dict['delete'] = effective config values, not in session
                 dict['add']    = session config values, not in effective
                 dict['stable'] = config values in both session and effective
        """
        session_dict = get_sub_dict(self._session_config_dict,
                                    self._make_path(path), get_first_key=True)

        if recursive:
            if self._diff_tree is None:
                raise NotImplementedError("diff_tree class not available")
            else:
                add = get_sub_dict(self._diff_dict, ['add'], get_first_key=True)
                sub = get_sub_dict(self._diff_dict, ['sub'], get_first_key=True)
                inter = get_sub_dict(self._diff_dict, ['inter'], get_first_key=True)
                ret = {}
                ret[enum_to_key(Diff.MERGE)] = session_dict
                ret[enum_to_key(Diff.DELETE)] = get_sub_dict(sub, self._make_path(path),
                                                             get_first_key=True)
                ret[enum_to_key(Diff.ADD)] = get_sub_dict(add, self._make_path(path),
                                                          get_first_key=True)
                ret[enum_to_key(Diff.STABLE)] = get_sub_dict(inter, self._make_path(path),
                                                             get_first_key=True)
                for e in Diff:
                    k = enum_to_key(e)
                    if not (e & expand_nodes):
                        ret[k] = list(ret[k])
                    else:
                        if self._key_mangling:
                            ret[k] = self._mangle_dict_keys(ret[k])
                        if k in target_defaults and not no_defaults:
                            default_values = get_defaults(self._make_path(path),
                                                          get_first_key=True,
                                                          recursive=True)
                            ret[k] = dict_merge(default_values, ret[k])
                return ret

        effective_dict = get_sub_dict(self._effective_config_dict,
                                      self._make_path(path), get_first_key=True)

        ret = _key_sets_from_dicts(session_dict, effective_dict)

        if not expand_nodes:
            return ret

        for e in Diff:
            if expand_nodes & e:
                k = enum_to_key(e)
                if k in requires_effective:
                    ret[k] = _dict_from_key_set(ret[k], effective_dict)
                else:
                    ret[k] = _dict_from_key_set(ret[k], session_dict)

                if self._key_mangling:
                    ret[k] = self._mangle_dict_keys(ret[k])

                if k in target_defaults and not no_defaults:
                    default_values = get_defaults(self._make_path(path),
                                                  get_first_key=True,
                                                  recursive=True)
                    ret[k] = dict_merge(default_values, ret[k])

        return ret

    def get_node_diff(self, path=[], expand_nodes=Diff(0), no_defaults=False,
                      recursive=False):
        """
        Args:
            path (str|list): config path
            expand_nodes=Diff(0): bit mask of enum indicating for which nodes
                                  to provide full dict; for example, Diff.MERGE
                                  will expand dict['merge'] into dict under
                                  value
            no_detaults=False: if expand_nodes & Diff.MERGE, do not merge default
                               values to ret['merge']
            recursive: if true, use config_tree diff algorithm provided by
                       diff_tree class

        Returns: dict of lists, representing differences between session
                                and effective config, at path
                 dict['merge']  = session config values
                 dict['delete'] = effective config values, not in session
                 dict['add']    = session config values, not in effective
                 dict['stable'] = config values in both session and effective
        """
        session_dict = get_sub_dict(self._session_config_dict, self._make_path(path))

        if recursive:
            if self._diff_tree is None:
                raise NotImplementedError("diff_tree class not available")
            else:
                add = get_sub_dict(self._diff_dict, ['add'], get_first_key=True)
                sub = get_sub_dict(self._diff_dict, ['sub'], get_first_key=True)
                inter = get_sub_dict(self._diff_dict, ['inter'], get_first_key=True)
                ret = {}
                ret[enum_to_key(Diff.MERGE)] = session_dict
                ret[enum_to_key(Diff.DELETE)] = get_sub_dict(sub, self._make_path(path))
                ret[enum_to_key(Diff.ADD)] = get_sub_dict(add, self._make_path(path))
                ret[enum_to_key(Diff.STABLE)] = get_sub_dict(inter, self._make_path(path))
                for e in Diff:
                    k = enum_to_key(e)
                    if not (e & expand_nodes):
                        ret[k] = list(ret[k])
                    else:
                        if self._key_mangling:
                            ret[k] = self._mangle_dict_keys(ret[k])
                        if k in target_defaults and not no_defaults:
                            default_values = get_defaults(self._make_path(path),
                                                          get_first_key=True,
                                                          recursive=True)
                            ret[k] = dict_merge(default_values, ret[k])
                return ret

        effective_dict = get_sub_dict(self._effective_config_dict, self._make_path(path))

        ret = _key_sets_from_dicts(session_dict, effective_dict)

        if not expand_nodes:
            return ret

        for e in Diff:
            if expand_nodes & e:
                k = enum_to_key(e)
                if k in requires_effective:
                    ret[k] = _dict_from_key_set(ret[k], effective_dict)
                else:
                    ret[k] = _dict_from_key_set(ret[k], session_dict)

                if self._key_mangling:
                    ret[k] = self._mangle_dict_keys(ret[k])

                if k in target_defaults and not no_defaults:
                    default_values = get_defaults(self._make_path(path),
                                                  get_first_key=True,
                                                  recursive=True)
                    ret[k] = dict_merge(default_values, ret[k])

        return ret

    def get_value_diff(self, path=[]):
        """
        Args:
            path (str|list): config path

        Returns: (new, old) tuple of values in session config/effective config
        """
        # one should properly use is_leaf as check; for the moment we will
        # deduce from type, which will not catch call on non-leaf node if None
        new_value_dict = get_sub_dict(self._session_config_dict, self._make_path(path))
        old_value_dict = get_sub_dict(self._effective_config_dict, self._make_path(path))

        new_value = None
        old_value = None
        if new_value_dict:
            new_value = next(iter(new_value_dict.values()))
        if old_value_dict:
            old_value = next(iter(old_value_dict.values()))

        if new_value and isinstance(new_value, dict):
            raise ConfigDiffError("get_value_changed called on non-leaf node")
        if old_value and isinstance(old_value, dict):
            raise ConfigDiffError("get_value_changed called on non-leaf node")

        return new_value, old_value
