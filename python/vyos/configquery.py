# Copyright 2021-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import json
import subprocess

from vyos.utils.process import STDOUT
from vyos.utils.process import popen

from vyos.utils.boot import boot_configuration_complete
from vyos.config import Config
from vyos.configsource import ConfigSourceSession, ConfigSourceString
from vyos.defaults import directories
from vyos.configtree import ConfigTree
from vyos.utils.dict import embed_dict
from vyos.utils.dict import get_sub_dict
from vyos.utils.dict import mangle_dict_keys
from vyos.utils.error import cli_shell_api_err
from vyos.xml_ref import multi_to_list
from vyos.xml_ref import is_tag
from vyos.base import Warning

config_file = os.path.join(directories['config'], 'config.boot')

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
        (_, err) = popen(f'cli-shell-api existsActive {cmd}')
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

class ConfigTreeQuery(GenericConfigQuery):
    def __init__(self):
        super().__init__()

        if boot_configuration_complete():
            config_source = ConfigSourceSession()
            self.config = Config(config_source=config_source)
        else:
            try:
                with open(config_file) as f:
                    config_string = f.read()
            except OSError as err:
                config_string = ''

            config_source = ConfigSourceString(running_config_text=config_string,
                                               session_config_text=config_string)
            self.config = Config(config_source=config_source)

    def exists(self, path: list):
        return self.config.exists(path)

    def value(self, path: list):
        return self.config.return_value(path)

    def values(self, path: list):
        return self.config.return_values(path)

    def list_nodes(self, path: list):
        return self.config.list_nodes(path)

    def get_config_dict(self, path=[], effective=False, key_mangling=None,
                        get_first_key=False, no_multi_convert=False,
                        no_tag_node_value_mangle=False):
        return self.config.get_config_dict(path, effective=effective,
                key_mangling=key_mangling, get_first_key=get_first_key,
                no_multi_convert=no_multi_convert,
                no_tag_node_value_mangle=no_tag_node_value_mangle)

class VbashOpRun(GenericOpRun):
    def __init__(self):
        super().__init__()

    def run(self, path: list, **kwargs):
        cmd = ' '.join(path)
        (out, err) = popen(f'/opt/vyatta/bin/vyatta-op-cmd-wrapper {cmd}', stderr=STDOUT, **kwargs)
        if err:
            raise ConfigQueryError(out)
        return out

def query_context(config_query_class=CliShellApiConfigQuery,
                  op_run_class=VbashOpRun):
    query = config_query_class()
    run = op_run_class()
    return query, run

def verify_mangling(key_mangling):
    if not (isinstance(key_mangling, tuple) and
            len(key_mangling) == 2 and
            isinstance(key_mangling[0], str) and
            isinstance(key_mangling[1], str)):
        raise ValueError("key_mangling must be a tuple of two strings")

def op_mode_run(cmd):
    """ low-level to avoid overhead  """
    p = subprocess.Popen(cmd, stdout=subprocess.PIPE)
    out = p.stdout.read()
    p.wait()
    return p.returncode, out.decode()

def op_mode_config_dict(path=None, key_mangling=None,
                        no_tag_node_value_mangle=False,
                        no_multi_convert=False, get_first_key=False):

    if path is None:
        path = []
    command = ['/bin/cli-shell-api', '--show-active-only', 'showConfig']

    rc, out = op_mode_run(command + path)
    if rc == cli_shell_api_err.VYOS_EMPTY_CONFIG:
        out = ''
    if rc == cli_shell_api_err.VYOS_INVALID_PATH:
        Warning(out)
        return {}

    ct = ConfigTree(out)
    d = json.loads(ct.to_json())
    # cli-shell-api output includes last path component if tag node
    if is_tag(path):
        config_dict = embed_dict(path[:-1], d)
    else:
        config_dict = embed_dict(path, d)

    if not no_multi_convert:
        config_dict = multi_to_list([], config_dict)

    if key_mangling is not None:
        verify_mangling(key_mangling)
        config_dict = mangle_dict_keys(config_dict,
                                       key_mangling[0], key_mangling[1],
                                       no_tag_node_value_mangle=no_tag_node_value_mangle)

    return get_sub_dict(config_dict, path, get_first_key=get_first_key)
