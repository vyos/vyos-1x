# Copyright 2021-2022 VyOS maintainers and contributors <maintainers@vyos.io>
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

import os
import json

from ariadne import convert_camel_case_to_snake

from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.defaults import directories
from vyos.template import render
from vyos.opmode import Error as OpModeError

from api.graphql.libs.op_mode import load_op_mode_as_module, split_compound_op_mode_name
from api.graphql.libs.op_mode import normalize_output

op_mode_include_file = os.path.join(directories['data'], 'op-mode-standardized.json')

class Session:
    """
    Wrapper for calling configsession functions based on GraphQL requests.
    Non-nullable fields in the respective schema allow avoiding a key check
    in 'data'.
    """
    def __init__(self, session, data):
        self._session = session
        self._data = data
        self._name = convert_camel_case_to_snake(type(self).__name__)

        try:
            with open(op_mode_include_file) as f:
                self._op_mode_list = json.loads(f.read())
        except Exception:
            self._op_mode_list = None

    def show_config(self):
        session = self._session
        data = self._data
        out = ''

        try:
            out = session.show_config(data['path'])
            if data.get('config_format', '') == 'json':
                config_tree = ConfigTree(out)
                out = json.loads(config_tree.to_json())
        except Exception as error:
            raise error

        return out

    def save_config_file(self):
        session = self._session
        data = self._data
        if 'file_name' not in data or not data['file_name']:
            data['file_name'] = '/config/config.boot'

        try:
            session.save_config(data['file_name'])
        except Exception as error:
            raise error

    def load_config_file(self):
        session = self._session
        data = self._data

        try:
            session.load_config(data['file_name'])
            session.commit()
        except Exception as error:
            raise error

    def show(self):
        session = self._session
        data = self._data
        out = ''

        try:
            out = session.show(data['path'])
        except Exception as error:
            raise error

        return out

    def add_system_image(self):
        session = self._session
        data = self._data

        try:
            res = session.install_image(data['location'])
        except Exception as error:
            raise error

        return res

    def delete_system_image(self):
        session = self._session
        data = self._data

        try:
            res = session.remove_image(data['name'])
        except Exception as error:
            raise error

        return res

    def system_status(self):
        import api.graphql.session.composite.system_status as system_status

        session = self._session
        data = self._data

        status = {}
        status['host_name'] = session.show(['host', 'name']).strip()
        status['version'] = system_status.get_system_version()
        status['uptime'] = system_status.get_system_uptime()
        status['ram'] = system_status.get_system_ram_usage()

        return status

    def gen_op_query(self):
        session = self._session
        data = self._data
        name = self._name
        op_mode_list = self._op_mode_list

        # handle the case that the op-mode file contains underscores:
        if op_mode_list is None:
            raise FileNotFoundError(f"No op-mode file list at '{op_mode_include_file}'")
        (func_name, scriptname) = split_compound_op_mode_name(name, op_mode_list)
        if scriptname == '':
            raise FileNotFoundError(f"No op-mode file named in string '{name}'")

        mod = load_op_mode_as_module(f'{scriptname}')
        func = getattr(mod, func_name)
        try:
            res = func(True, **data)
        except OpModeError as e:
            raise e

        res = normalize_output(res)

        return res

    def gen_op_mutation(self):
        session = self._session
        data = self._data
        name = self._name
        op_mode_list = self._op_mode_list

        # handle the case that the op-mode file name contains underscores:
        if op_mode_list is None:
            raise FileNotFoundError(f"No op-mode file list at '{op_mode_include_file}'")
        (func_name, scriptname) = split_compound_op_mode_name(name, op_mode_list)
        if scriptname == '':
            raise FileNotFoundError(f"No op-mode file named in string '{name}'")

        mod = load_op_mode_as_module(f'{scriptname}')
        func = getattr(mod, func_name)
        try:
            res = func(**data)
        except OpModeError as e:
            raise e

        return res
