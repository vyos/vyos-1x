import re


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
    key_value_re = re.compile('([^:]+)\s*\:\s*(.*)')

    data_raw = re.split('\n', data_string)

    data = {}

    for l in data_raw:
        l = l.strip()
        if l:
            match = re.match(key_value_re, l)
            if match:
                key = match.groups()[0].strip()
                value = match.groups()[1].strip()
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
