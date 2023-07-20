# Copyright 2023 VyOS maintainers and contributors <maintainers@vyos.io>
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

from typing import Optional, Union, Any, TYPE_CHECKING

# https://peps.python.org/pep-0484/#forward-references
# for type 'ConfigDict'
if TYPE_CHECKING:
    from vyos.config import ConfigDict

class Xml:
    def __init__(self):
        self.ref = {}

    def define(self, ref: dict):
        self.ref = ref

    def _get_ref_node_data(self, node: dict, data: str) -> Union[bool, str]:
        res = node.get('node_data', {})
        if not res:
            raise ValueError("non-existent node data")
        if data not in res:
            raise ValueError("non-existent data field")

        return res.get(data)

    def _get_ref_path(self, path: list) -> dict:
        ref_path = path.copy()
        d = self.ref
        while ref_path and d:
            d = d.get(ref_path[0], {})
            ref_path.pop(0)
            if self._is_tag_node(d) and ref_path:
                ref_path.pop(0)

        return d

    def _is_tag_node(self, node: dict) -> bool:
        res = self._get_ref_node_data(node, 'node_type')
        return res == 'tag'

    def is_tag(self, path: list) -> bool:
        ref_path = path.copy()
        d = self.ref
        while ref_path and d:
            d = d.get(ref_path[0], {})
            ref_path.pop(0)
            if self._is_tag_node(d) and ref_path:
                if len(ref_path) == 1:
                    return False
                ref_path.pop(0)

        return self._is_tag_node(d)

    def is_tag_value(self, path: list) -> bool:
        if len(path) < 2:
            return False

        return self.is_tag(path[:-1])

    def _is_multi_node(self, node: dict) -> bool:
        b = self._get_ref_node_data(node, 'multi')
        assert isinstance(b, bool)
        return b

    def is_multi(self, path: list) -> bool:
        d = self._get_ref_path(path)
        return  self._is_multi_node(d)

    def _is_valueless_node(self, node: dict) -> bool:
        b = self._get_ref_node_data(node, 'valueless')
        assert isinstance(b, bool)
        return b

    def is_valueless(self, path: list) -> bool:
        d = self._get_ref_path(path)
        return  self._is_valueless_node(d)

    def _is_leaf_node(self, node: dict) -> bool:
        res = self._get_ref_node_data(node, 'node_type')
        return res == 'leaf'

    def is_leaf(self, path: list) -> bool:
        d = self._get_ref_path(path)
        return self._is_leaf_node(d)

    @staticmethod
    def _dict_get(d: dict, path: list) -> dict:
        for i in path:
            d = d.get(i, {})
            if not isinstance(d, dict):
                return {}
            if not d:
                break
        return d

    def _dict_find(self, d: dict, key: str, non_local=False) -> bool:
        for k in list(d):
            if k in ('node_data', 'component_version'):
                continue
            if k == key:
                return True
            if non_local and isinstance(d[k], dict):
                if self._dict_find(d[k], key):
                    return True
        return False

    def cli_defined(self, path: list, node: str, non_local=False) -> bool:
        d = self._dict_get(self.ref, path)
        return self._dict_find(d, node, non_local=non_local)

    def component_version(self) -> dict:
        d = {}
        for k, v in self.ref['component_version']:
            d[k] = int(v)
        return d

    def multi_to_list(self, rpath: list, conf: dict) -> dict:
        res: Any = {}

        for k in list(conf):
            d = self._get_ref_path(rpath + [k])
            if self._is_leaf_node(d):
                if self._is_multi_node(d) and not isinstance(conf[k], list):
                    res[k] = [conf[k]]
                else:
                    res[k] = conf[k]
            else:
                res[k] = self.multi_to_list(rpath + [k], conf[k])

        return res

    def _get_default_value(self, node: dict) -> Optional[str]:
        return self._get_ref_node_data(node, "default_value")

    def _get_default(self, node: dict) -> Optional[Union[str, list]]:
        default = self._get_default_value(node)
        if default is None:
            return None
        if self._is_multi_node(node):
            return default.split()
        return default

    def get_defaults(self, path: list, get_first_key=False, recursive=False) -> dict:
        """Return dict containing default values below path

        Note that descent below path will not proceed beyond an encountered
        tag node, as no tag node value is known. For a default dict relative
        to an existing config dict containing tag node values, see function:
        'relative_defaults'
        """
        res: dict = {}
        if self.is_tag(path):
            return res

        d = self._get_ref_path(path)

        if self._is_leaf_node(d):
            default_value = self._get_default(d)
            if default_value is not None:
                return {path[-1]: default_value} if path else {}

        for k in list(d):
            if k in ('node_data', 'component_version') :
                continue
            if self._is_leaf_node(d[k]):
                default_value = self._get_default(d[k])
                if default_value is not None:
                    res |= {k: default_value}
            elif self.is_tag(path + [k]):
                # tag node defaults are used as suggestion, not default value;
                # should this change, append to path and continue if recursive
                pass
            else:
                if recursive:
                    pos = self.get_defaults(path + [k], recursive=True)
                    res |= pos
        if res:
            if get_first_key or not path:
                return res
            return {path[-1]: res}

        return {}

    def _well_defined(self, path: list, conf: dict) -> bool:
        # test disjoint path + conf for sensible config paths
        def step(c):
            return [next(iter(c.keys()))] if c else []
        try:
            tmp = step(conf)
            if tmp and self.is_tag_value(path + tmp):
                c = conf[tmp[0]]
                if not isinstance(c, dict):
                    raise ValueError
                tmp = tmp + step(c)
                self._get_ref_path(path + tmp)
            else:
                self._get_ref_path(path + tmp)
        except ValueError:
            return False
        return True

    def _set_source_recursive(self, o: Union[dict, str, list], b: bool):
        d = {}
        if not isinstance(o, dict):
            d = {'_source': b}
        else:
            for k, v in o.items():
                d[k] = self._set_source_recursive(v, b)
            d |= {'_source': b}
        return d

    # use local copy of function in module configdict, to avoid circular
    # import
    #
    # extend dict_merge to keep track of keys only in source
    def _dict_merge(self, source, destination):
        from copy import deepcopy
        dest = deepcopy(destination)
        from_source = {}

        for key, value in source.items():
            if key not in dest:
                dest[key] = value
                from_source[key] = self._set_source_recursive(value, True)
            elif isinstance(source[key], dict):
                dest[key], f = self._dict_merge(source[key], dest[key])
                f |= {'_source': False}
                from_source[key] = f

        return dest, from_source

    def from_source(self, d: dict, path: list) -> bool:
        for key in path:
            d  = d[key] if key in d else {}
            if not d or not isinstance(d, dict):
                return False
        return d.get('_source', False)

    def _relative_defaults(self, rpath: list, conf: dict, recursive=False) -> dict:
        res: dict = {}
        res = self.get_defaults(rpath, recursive=recursive,
                                get_first_key=True)
        for k in list(conf):
            if isinstance(conf[k], dict):
                step = self._relative_defaults(rpath + [k], conf=conf[k],
                                               recursive=recursive)
                res |= step

        if res:
            return {rpath[-1]: res} if rpath else res

        return {}

    def relative_defaults(self, path: list, conf: dict, get_first_key=False,
                          recursive=False) -> dict:
        """Return dict containing defaults along paths of a config dict
        """
        if not conf:
            return self.get_defaults(path, get_first_key=get_first_key,
                                     recursive=recursive)
        if not self._well_defined(path, conf):
            # adjust for possible overlap:
            if path and path[-1] in list(conf):
                conf = conf[path[-1]]
                conf = {} if not isinstance(conf, dict) else conf
            if not self._well_defined(path, conf):
                print('path to config dict does not define full config paths')
                return {}

        res = self._relative_defaults(path, conf, recursive=recursive)

        if get_first_key and path:
            if res.values():
                res = next(iter(res.values()))
            else:
                res = {}

        return res

    def merge_defaults(self, path: list, conf: Union[dict, 'ConfigDict'],
                       get_first_key=False, recursive=False) -> dict:
        """Return config dict with defaults non-destructively merged

        This merges non-recursive defaults relative to the config dict.
        """
        d = self.relative_defaults(path, conf, get_first_key=get_first_key,
                                   recursive=recursive)
        d, f = self._dict_merge(d, conf)
        d = type(conf)(d)
        if hasattr(d, '_from_defaults'):
            setattr(d, '_from_defaults', f)
        return d
