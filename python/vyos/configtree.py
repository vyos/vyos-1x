# configtree -- a standalone VyOS config file manipulation library (Python bindings)
# Copyright (C) 2018 VyOS maintainers and contributors
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

import re
import json

from ctypes import cdll, c_char_p, c_void_p, c_int


def strip_comments(s):
    """ Split a config string into the config section and the trailing comments """
    INITIAL = 0
    IN_COMMENT = 1

    i = len(s) - 1

    state = INITIAL

    config_end = 0

    # Find the first character of the comments section at the end,
    # if it exists
    while (i >= 0):
        c = s[i]

        if (state == INITIAL) and re.match(r'\s', c):
            # Ignore whitespace
            if (i != 0):
                i -= 1
            else:
                config_end = 0
                break
        elif (state == INITIAL) and not re.match(r'(\s|\/)', c):
            # Assume there are no (more) trailing comments,
            # this is an end of a node: either a brace of the last character
            # of a leaf node value
            config_end = i + 1
            break
        elif (state == INITIAL) and (c == '/'):
            # A comment begins, or it's a stray slash
            if (s[i-1] == '*'):
                state = IN_COMMENT
                i -= 2
            else:
                raise ValueError("Invalid syntax: stray slash at character {0}".format(i + 1))
        elif (state == IN_COMMENT) and (c == '*'):
            # A comment ends here
            try:
                if (s[i-1] == '/'):
                    state = INITIAL
                    i -= 2
            except:
                raise ValueError("Invalid syntax: malformed commend end at character {0}".format(i + 1))
        elif (state == IN_COMMENT) and (c != '*'):
            # Ignore everything inside comments, including braces
            i -= 1
        else:
            # Shouldn't happen
            raise ValueError("Invalid syntax at character {0}: invalid character {1}".format(i + 1, c))

    return (s[0:config_end], s[config_end+1:])

def check_path(path):
    # Necessary type checking
    if not isinstance(path, list):
        raise TypeError("Expected a list, got a {}".format(type(path)))
    else:
        pass


class ConfigTreeError(Exception):
    pass


class ConfigTree(object):
    def __init__(self, config_string, libpath='/usr/lib/libvyosconfig.so.0'):
        self.__config = None
        self.__lib = cdll.LoadLibrary(libpath)

        # Import functions
        self.__from_string = self.__lib.from_string
        self.__from_string.argtypes = [c_char_p]
        self.__from_string.restype = c_void_p

        self.__get_error = self.__lib.get_error
        self.__get_error.argtypes = []
        self.__get_error.restype = c_char_p

        self.__to_string = self.__lib.to_string
        self.__to_string.argtypes = [c_void_p]
        self.__to_string.restype = c_char_p

        self.__to_commands = self.__lib.to_commands
        self.__to_commands.argtypes = [c_void_p]
        self.__to_commands.restype = c_char_p

        self.__set_add_value = self.__lib.set_add_value
        self.__set_add_value.argtypes = [c_void_p, c_char_p, c_char_p]
        self.__set_add_value.restype = c_int

        self.__delete_value = self.__lib.delete_value
        self.__delete_value.argtypes = [c_void_p, c_char_p, c_char_p]
        self.__delete_value.restype = c_int

        self.__delete = self.__lib.delete_node
        self.__delete.argtypes = [c_void_p, c_char_p]
        self.__delete.restype = c_int

        self.__rename = self.__lib.rename_node
        self.__rename.argtypes = [c_void_p, c_char_p, c_char_p]
        self.__rename.restype = c_int

        self.__copy = self.__lib.copy_node
        self.__copy.argtypes = [c_void_p, c_char_p, c_char_p]
        self.__copy.restype = c_int

        self.__set_replace_value = self.__lib.set_replace_value
        self.__set_replace_value.argtypes = [c_void_p, c_char_p, c_char_p]
        self.__set_replace_value.restype = c_int

        self.__set_valueless = self.__lib.set_valueless
        self.__set_valueless.argtypes = [c_void_p, c_char_p]
        self.__set_valueless.restype = c_int

        self.__exists = self.__lib.exists
        self.__exists.argtypes = [c_void_p, c_char_p]
        self.__exists.restype = c_int

        self.__list_nodes = self.__lib.list_nodes
        self.__list_nodes.argtypes = [c_void_p, c_char_p]
        self.__list_nodes.restype = c_char_p

        self.__return_value = self.__lib.return_value
        self.__return_value.argtypes = [c_void_p, c_char_p]
        self.__return_value.restype = c_char_p

        self.__return_values = self.__lib.return_values
        self.__return_values.argtypes = [c_void_p, c_char_p]
        self.__return_values.restype = c_char_p

        self.__is_tag = self.__lib.is_tag
        self.__is_tag.argtypes = [c_void_p, c_char_p]
        self.__is_tag.restype = c_int

        self.__set_tag = self.__lib.set_tag
        self.__set_tag.argtypes = [c_void_p, c_char_p]
        self.__set_tag.restype = c_int

        self.__destroy = self.__lib.destroy
        self.__destroy.argtypes = [c_void_p]

        config_section, comments_section = strip_comments(config_string)
        config = self.__from_string(config_section.encode())
        if config is None:
            msg = self.__get_error().decode()
            raise ValueError("Failed to parse config: {0}".format(msg))
        else:
            self.__config = config
            self.__comments = comments_section

    def __del__(self):
        if self.__config is not None:
            self.__destroy(self.__config)

    def __str__(self):
        return self.to_string()

    def to_string(self):
        config_string = self.__to_string(self.__config).decode()
        config_string = "{0}\n{1}".format(config_string, self.__comments)
        return config_string

    def to_commands(self):
        return self.__to_commands(self.__config).decode()

    def set(self, path, value=None, replace=True):
        """Set new entry in VyOS configuration.
        path: configuration path e.g. 'system dns forwarding listen-address'
        value: value to be added to node, e.g. '172.18.254.201'
        replace: True: current occurance will be replaced
                 False: new value will be appended to current occurances - use
                 this for adding values to a multi node
        """

        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        if value is None:
            self.__set_valueless(self.__config, path_str)
        else:
            if replace:
                self.__set_replace_value(self.__config, path_str, str(value).encode())
            else:
                self.__set_add_value(self.__config, path_str, str(value).encode())

    def delete(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        self.__delete(self.__config, path_str)

    def delete_value(self, path, value):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        self.__delete_value(self.__config, path_str, value.encode())

    def rename(self, path, new_name):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()
        newname_str = new_name.encode()

        # Check if a node with intended new name already exists
        new_path = path[:-1] + [new_name]
        if self.exists(new_path):
            raise ConfigTreeError()
        res = self.__rename(self.__config, path_str, newname_str)
        if (res != 0):
            raise ConfigTreeError("Path [{}] doesn't exist".format(oldpath))

    def copy(self, old_path, new_path):
        check_path(old_path)
        check_path(new_path)
        oldpath_str = " ".join(map(str, old_path)).encode()
        newpath_str = " ".join(map(str, new_path)).encode()

        # Check if a node with intended new name already exists
        if self.exists(new_path):
            raise ConfigTreeError()
        res = self.__copy(self.__config, oldpath_str, newpath_str)
        if (res != 0):
            raise ConfigTreeError("Path [{}] doesn't exist".format(oldpath))

    def exists(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res = self.__exists(self.__config, path_str)
        if (res == 0):
            return False
        else:
            return True

    def list_nodes(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res_json = self.__list_nodes(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            raise ConfigTreeError("Path [{}] doesn't exist".format(path_str))
        else:
            return res

    def return_value(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res_json = self.__return_value(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            raise ConfigTreeError("Path [{}] doesn't exist".format(path_str))
        else:
            return res

    def return_values(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res_json = self.__return_values(self.__config, path_str).decode()
        res = json.loads(res_json)

        if res is None:
            raise ConfigTreeError("Path [{}] doesn't exist".format(path_str))
        else:
            return res

    def is_tag(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res = self.__is_tag(self.__config, path_str)
        if (res >= 1):
            return True
        else:
            return False

    def set_tag(self, path):
        check_path(path)
        path_str = " ".join(map(str, path)).encode()

        res = self.__set_tag(self.__config, path_str)
        if (res == 0):
            return True
        else:
            raise ConfigTreeError("Path [{}] doesn't exist".format(path_str))

