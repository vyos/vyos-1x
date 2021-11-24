from ariadne import convert_camel_case_to_snake
import vyos.defaults
from vyos.template import render

class Recipe(object):
    def __init__(self, session, data):
        self._session = session
        self.data = data
        self._name = convert_camel_case_to_snake(type(self).__name__)

    @property
    def data(self):
        return self.__data

    @data.setter
    def data(self, data):
        if isinstance(data, dict):
            self.__data = data
        else:
            raise ValueError("data must be of type dict")

    def configure(self):
        session = self._session
        data = self.data
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

    def save(self):
        session = self._session
        data = self.data
        if 'file_name' not in data or not data['file_name']:
            data['file_name'] = '/config/config.boot'

        try:
            session.save_config(data['file_name'])
        except Exception as error:
            raise error

    def load(self):
        session = self._session
        data = self.data

        try:
            session.load_config(data['file_name'])
            session.commit()
        except Exception as error:
            raise error
