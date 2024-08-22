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
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

def colon_separated_to_dict(data_string, uniquekeys=False):
    """ Converts a string containing newline-separated entries
        of colon-separated key-value pairs into a dict.

        Such files are common in Linux /proc filesystem

    Args:
        data_string (str): data string
        uniquekeys (bool): whether to insist that keys are unique or not

    Returns: dict

    Raises:
        ValueError: if uniquekeys=True and the data string has
            duplicate keys.

    Note:
        If uniquekeys=True, then dict entries are always strings,
        otherwise they are always lists of strings.
    """
    import re
    key_value_re = re.compile(r'([^:]+)\s*\:\s*(.*)')

    data_raw = re.split('\n', data_string)

    data = {}

    for l in data_raw:
        l = l.strip()
        if l:
            match = re.match(key_value_re, l)
            if match and (len(match.groups()) == 2):
                key = match.groups()[0].strip()
                value = match.groups()[1].strip()
            else:
                raise ValueError(f"""Line "{l}" could not be parsed a colon-separated pair """, l)
            if key in data.keys():
                if uniquekeys:
                    raise ValueError("Data string has duplicate keys: {0}".format(key))
                else:
                    data[key].append(value)
            else:
                if uniquekeys:
                    data[key] = value
                else:
                    data[key] = [value]
        else:
            pass

    return data

def mangle_dict_keys(data, regex, replacement, abs_path=None, no_tag_node_value_mangle=False):
    """ Mangles dict keys according to a regex and replacement character.
    Some libraries like Jinja2 do not like certain characters in dict keys.
    This function can be used for replacing all offending characters
    with something acceptable.

    Args:
        data (dict): Original dict to mangle
        regex, replacement (str): arguments to re.sub(regex, replacement, ...)
        abs_path (list): if data is a config dict and no_tag_node_value_mangle is True
                         then abs_path should be the absolute config path to the first
                         keys of data, non-inclusive
        no_tag_node_value_mangle (bool): do not mangle keys of tag node values

    Returns: dict
    """
    import re
    from vyos.xml_ref import is_tag_value

    if abs_path is None:
        abs_path = []

    new_dict = type(data)()

    for k in data.keys():
        if no_tag_node_value_mangle and is_tag_value(abs_path + [k]):
            new_key = k
        else:
            new_key = re.sub(regex, replacement, k)

        value = data[k]

        if isinstance(value, dict):
            new_dict[new_key] = mangle_dict_keys(value, regex, replacement,
                                                 abs_path=abs_path + [k],
                                                 no_tag_node_value_mangle=no_tag_node_value_mangle)
        else:
            new_dict[new_key] = value

    return new_dict

def _get_sub_dict(d, lpath):
    k = lpath[0]
    if k not in d.keys():
        return {}
    c = {k: d[k]}
    lpath = lpath[1:]
    if not lpath:
        return c
    elif not isinstance(c[k], dict):
        return {}
    return _get_sub_dict(c[k], lpath)

def get_sub_dict(source, lpath, get_first_key=False):
    """ Returns the sub-dict of a nested dict, defined by path of keys.

    Args:
        source (dict): Source dict to extract from
        lpath (list[str]): sequence of keys

    Returns: source, if lpath is empty, else
             {key : source[..]..[key]} for key the last element of lpath, if exists
             {} otherwise
    """
    if not isinstance(source, dict):
        raise TypeError("source must be of type dict")
    if not isinstance(lpath, list):
        raise TypeError("path must be of type list")
    if not lpath:
        return source

    ret =  _get_sub_dict(source, lpath)

    if get_first_key and lpath and ret:
        tmp = next(iter(ret.values()))
        if not isinstance(tmp, dict):
            raise TypeError("Data under node is not of type dict")
        ret = tmp

    return ret

def dict_search(path, dict_object):
    """ Traverse Python dictionary (dict_object) delimited by dot (.).
    Return value of key if found, None otherwise.

    This is faster implementation then jmespath.search('foo.bar', dict_object)"""
    if not isinstance(dict_object, dict) or not path:
        return None

    parts = path.split('.')
    inside = parts[:-1]
    if not inside:
        if path not in dict_object:
            return None
        return dict_object[path]
    c = dict_object
    for p in parts[:-1]:
        c = c.get(p, {})
    return c.get(parts[-1], None)

def dict_search_args(dict_object, *path):
    # Traverse dictionary using variable arguments
    # Added due to above function not allowing for '.' in the key names
    # Example: dict_search_args(some_dict, 'key', 'subkey', 'subsubkey', ...)
    if not isinstance(dict_object, dict) or not path:
        return None

    for item in path:
        if item not in dict_object:
            return None
        dict_object = dict_object[item]
    return dict_object

def dict_search_recursive(dict_object, key, path=[]):
    """ Traverse a dictionary recurisvely and return the value of the key
    we are looking for.

    Thankfully copied from https://stackoverflow.com/a/19871956

    Modified to yield optional path to found keys
    """
    if isinstance(dict_object, list):
        for i in dict_object:
            new_path = path + [i]
            for x in dict_search_recursive(i, key, new_path):
                yield x
    elif isinstance(dict_object, dict):
        if key in dict_object:
            new_path = path + [key]
            yield dict_object[key], new_path
        for k, j in dict_object.items():
            new_path = path + [k]
            for x in dict_search_recursive(j, key, new_path):
                yield x


def dict_set(key_path, value, dict_object):
    """ Set value to Python dictionary (dict_object) using path to key delimited by dot (.).
        The key will be added if it does not exist.
    """
    path_list = key_path.split(".")
    dynamic_dict = dict_object
    if len(path_list) > 0:
        for i in range(0, len(path_list)-1):
            dynamic_dict = dynamic_dict[path_list[i]]
        dynamic_dict[path_list[len(path_list)-1]] = value

def dict_delete(key_path, dict_object):
    """ Delete key in Python dictionary (dict_object) using path to key delimited by dot (.).
    """
    path_dict = dict_object
    path_list = key_path.split('.')
    inside = path_list[:-1]
    if not inside:
        del dict_object[path_list]
    else:
        for key in path_list[:-1]:
            path_dict = path_dict[key]
        del path_dict[path_list[len(path_list)-1]]

def dict_to_list(d, save_key_to=None):
    """ Convert a dict to a list of dicts.

    Optionally, save the original key of the dict inside
    dicts stores in that list.
    """
    def save_key(i, k):
        if isinstance(i, dict):
            i[save_key_to] = k
            return
        elif isinstance(i, list):
            for _i in i:
                save_key(_i, k)
        else:
            raise ValueError(f"Cannot save the key: the item is {type(i)}, not a dict")

    collect = []

    for k,_ in d.items():
        item = d[k]
        if save_key_to is not None:
            save_key(item, k)
        if isinstance(item, list):
            collect += item
        else:
            collect.append(item)

    return collect

def dict_to_paths_values(conf: dict) -> dict:
    """
    Convert nested dictionary to simple dictionary, where key is a path is delimited by dot (.).
    """
    list_of_paths = []
    dict_of_options ={}
    for path in dict_to_key_paths(conf):
        str_path = '.'.join(path)
        list_of_paths.append(str_path)

    for path in list_of_paths:
        dict_of_options[path] = dict_search(path,conf)

    return dict_of_options

def dict_to_key_paths(d: dict) -> list:
    """ Generator to return list of key paths from dict of list[str]|str
    """
    def func(d, path):
        if isinstance(d, dict):
            if not d:
                yield path
            for k, v in d.items():
                for r in func(v, path + [k]):
                    yield r
        elif isinstance(d, list):
            yield path
        elif isinstance(d, str):
            yield path
        else:
            raise ValueError('object is not a dict of strings/list of strings')
    for r in func(d, []):
        yield r

def dict_to_paths(d: dict) -> list:
    """ Generator to return list of paths from dict of list[str]|str
    """
    def func(d, path):
        if isinstance(d, dict):
            if not d:
                yield path
            for k, v in d.items():
                for r in func(v, path + [k]):
                    yield r
        elif isinstance(d, list):
            for i in d:
                for r in func(i, path):
                    yield r
        elif isinstance(d, str):
            yield path + [d]
        else:
            raise ValueError('object is not a dict of strings/list of strings')
    for r in func(d, []):
        yield r

def embed_dict(p: list[str], d: dict) -> dict:
    path = p.copy()
    ret = d
    while path:
        ret = {path.pop(): ret}
    return ret

def check_mutually_exclusive_options(d, keys, required=False):
    """ Checks if a dict has at most one or only one of
    mutually exclusive keys.
    """
    present_keys = []

    for k in d:
        if k in keys:
            present_keys.append(k)

    # Un-mangle the keys to make them match CLI option syntax
    from re import sub
    orig_keys = list(map(lambda s: sub(r'_', '-', s), keys))
    orig_present_keys = list(map(lambda s: sub(r'_', '-', s), present_keys))

    if len(present_keys) > 1:
        raise ValueError(f"Options {orig_keys} are mutually-exclusive but more than one of them is present: {orig_present_keys}")

    if required and (len(present_keys) < 1):
        raise ValueError(f"At least one of the following options is required: {orig_keys}")

class FixedDict(dict):
    """
    FixedDict: A dictionnary not allowing new keys to be created after initialisation.

    >>> f = FixedDict(**{'count':1})
    >>> f['count'] = 2
    >>> f['king'] = 3
      File "...", line ..., in __setitem__
    raise ConfigError(f'Option "{k}" has no defined default')
    """

    from vyos import ConfigError

    def __init__(self, **options):
        self._allowed = options.keys()
        super().__init__(**options)

    def __setitem__(self, k, v):
        """
        __setitem__ is a builtin which is called by python when setting dict values:
        >>> d = dict()
        >>> d['key'] = 'value'
        >>> d
        {'key': 'value'}

        is syntaxic sugar for

        >>> d = dict()
        >>> d.__setitem__('key','value')
        >>> d
        {'key': 'value'}
        """
        if k not in self._allowed:
            raise ConfigError(f'Option "{k}" has no defined default')
        super().__setitem__(k, v)

