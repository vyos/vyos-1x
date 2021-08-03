# Copyright 2021 VyOS maintainers and contributors <maintainers@vyos.io>
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

'''
A small library that allows querying existence or value(s) of config
settings from op mode, and execution of arbitrary op mode commands.
'''

import re
import json
from subprocess import STDOUT

import vyos.util
import vyos.xml
from vyos.configtree import ConfigTree

class ConfigQueryError(Exception):
    pass

class GenericConfigQuery:
    def __init__(self):
        pass

    def exists(self, path: list):
        raise NotImplementedError

    def value(self, path: list):
        raise NotImplementedError

    def values(self, path: list):
        raise NotImplementedError

class GenericOpRun:
    def __init__(self):
        pass

    def run(self, path: list, **kwargs):
        raise NotImplementedError

class CliShellApiConfigQuery(GenericConfigQuery):
    def __init__(self):
        super().__init__()

    def exists(self, path: list):
        cmd = ' '.join(path)
        (_, err) = vyos.util.popen(f'cli-shell-api existsActive {cmd}')
        if err:
            return False
        return True

    def value(self, path: list):
        cmd = ' '.join(path)
        (out, err) = popen(f'cli-shell-api returnActiveValue {cmd}')
        if err:
            raise ConfigQueryError('No value for given path')
        return out

    def values(self, path: list):
        cmd = ' '.join(path)
        (out, err) = popen(f'cli-shell-api returnActiveValues {cmd}')
        if err:
            raise ConfigQueryError('No values for given path')
        return out

class ConfigTreeActiveQuery(GenericConfigQuery):
    def __init__(self):
        super().__init__()

        with open('/config/config.boot') as f:
            config_file = f.read()
        self.configtree = ConfigTree(config_file)

        self._level = []

    def exists(self, path: list):
        return self.configtree.exists(path)

    def value(self, path: list):
        return self.configtree.return_value(path)

    def values(self, path: list):
        return self.configtree.return_values(path)

    def list_nodes(self, path: list):
        return self.configtree.list_nodes(path)

    def _make_path(self, path):
        # Backwards-compatibility stuff: original implementation used string paths
        # libvyosconfig paths are lists, but since node names cannot contain whitespace,
        # splitting at whitespace is reasonably safe.
        # It may cause problems with exists() when it's used for checking values,
        # since values may contain whitespace.
        if isinstance(path, str):
            path = re.split(r'\s+', path)
        elif isinstance(path, list):
            pass
        else:
            raise TypeError("Path must be a whitespace-separated string or a list")
        return (self._level + path)

    def get_config_dict(self, path=[], key_mangling=None,
                        get_first_key=False, no_multi_convert=False,
                        no_tag_node_value_mangle=False):
        """
        Args:
            path (str list): Configuration tree path, can be empty
            key_mangling=None: mangle dict keys according to regex and replacement
            get_first_key=False: if k = path[:-1], return sub-dict d[k] instead of {k: d[k]}
            no_multi_convert=False: if convert, return single value of multi node as list

        Returns: a dict representation of the config under path
        """
        lpath = self._make_path(path)
        root_dict = json.loads(self.configtree.to_json())
        conf_dict = vyos.util.get_sub_dict(root_dict, lpath, get_first_key)

        if not key_mangling and no_multi_convert:
            return deepcopy(conf_dict)

        xmlpath = lpath if get_first_key else lpath[:-1]

        if not key_mangling:
            conf_dict = vyos.xml.multi_to_list(xmlpath, conf_dict)
            return conf_dict

        if no_multi_convert is False:
            conf_dict = multi_to_list(xmlpath, conf_dict)

        if not (isinstance(key_mangling, tuple) and \
                (len(key_mangling) == 2) and \
                isinstance(key_mangling[0], str) and \
                isinstance(key_mangling[1], str)):
            raise ValueError("key_mangling must be a tuple of two strings")

        conf_dict = vyos.util.mangle_dict_keys(conf_dict, key_mangling[0], key_mangling[1], abs_path=xmlpath, no_tag_node_value_mangle=no_tag_node_value_mangle)

        return conf_dict

class VbashOpRun(GenericOpRun):
    def __init__(self):
        super().__init__()

    def run(self, path: list, **kwargs):
        cmd = ' '.join(path)
        (out, err) = popen(f'.  /opt/vyatta/share/vyatta-op/functions/interpreter/vyatta-op-run; _vyatta_op_run {cmd}', stderr=STDOUT, **kwargs)
        if err:
            raise ConfigQueryError(out)
        return out

def query_context(config_query_class=CliShellApiConfigQuery,
                  op_run_class=VbashOpRun):
    query = config_query_class()
    run = op_run_class()
    return query, run


