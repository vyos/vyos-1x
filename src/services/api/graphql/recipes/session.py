import json

from ariadne import convert_camel_case_to_snake

import vyos.defaults
from vyos.config import Config
from vyos.configtree import ConfigTree
from vyos.template import render

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

    def configure(self):
        session = self._session
        data = self._data
        func_base_name = self._name

        tmpl_file = f'{func_base_name}.tmpl'
        cmd_file = f'/tmp/{func_base_name}.cmds'
        tmpl_dir = vyos.defaults.directories['api_templates']

        try:
            render(cmd_file, tmpl_file, data, location=tmpl_dir)
            commands = []
            with open(cmd_file) as f:
                lines = f.readlines()
            for line in lines:
                commands.append(line.split())
            for cmd in commands:
                if cmd[0] == 'set':
                    session.set(cmd[1:])
                elif cmd[0] == 'delete':
                    session.delete(cmd[1:])
                else:
                    raise ValueError('Operation must be "set" or "delete"')
            session.commit()
        except Exception as error:
            raise error

    def delete_path_if_childless(self, path):
        session = self._session
        config = Config(session.get_session_env())
        if not config.list_nodes(path):
            session.delete(path)
            session.commit()

    def show_config(self):
        session = self._session
        data = self._data
        out = ''

        try:
            out = session.show_config(data['path'])
            if data.get('config_format', '') == 'json':
                config_tree = vyos.configtree.ConfigTree(out)
                out = json.loads(config_tree.to_json())
        except Exception as error:
            raise error

        return out

    def save(self):
        session = self._session
        data = self._data
        if 'file_name' not in data or not data['file_name']:
            data['file_name'] = '/config/config.boot'

        try:
            session.save_config(data['file_name'])
        except Exception as error:
            raise error

    def load(self):
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

    def add(self):
        session = self._session
        data = self._data

        try:
            res = session.install_image(data['location'])
        except Exception as error:
            raise error

        return res

    def delete(self):
        session = self._session
        data = self._data

        try:
            res = session.remove_image(data['name'])
        except Exception as error:
            raise error

        return res
