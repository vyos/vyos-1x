# Copyright 2023-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

def seconds_to_human(s, separator=""):
    """ Converts number of seconds passed to a human-readable
    interval such as 1w4d18h35m59s
    """
    s = int(s)

    year = 60 * 60 * 24 * 365.25
    week = 60 * 60 * 24 * 7
    day = 60 * 60 * 24
    hour = 60 * 60

    result = []

    years = s // year
    if years > 0:
        result.append(f'{int(years)}y')
        s = int(s % year)

    weeks = s // week
    if weeks > 0:
        result.append(f'{weeks}w')
        s = s % week

    days = s // day
    if days > 0:
        result.append(f'{days}d')
        s = s % day

    hours = s // hour
    if hours > 0:
        result.append(f'{hours}h')
        s = s % hour

    minutes = s // 60
    if minutes > 0:
        result.append(f'{minutes}m')
        s = s % 60

    seconds = s
    if seconds > 0:
        result.append(f'{seconds}s')

    return separator.join(result)

def bytes_to_human(bytes, initial_exponent=0, precision=2,
                   int_below_exponent=0):
    """ Converts a value in bytes to a human-readable size string like 640 KB

    The initial_exponent parameter is the exponent of 2,
    e.g. 10 (1024) for kilobytes, 20 (1024 * 1024) for megabytes.
    """

    if bytes == 0:
        return "0 B"

    from math import log2

    bytes = bytes * (2**initial_exponent)

    # log2 is a float, while range checking requires an int
    exponent = int(log2(bytes))
    if exponent < int_below_exponent:
        precision = 0

    if exponent < 10:
        value = bytes
        suffix = "B"
    elif exponent in range(10, 20):
        value = bytes / 1024
        suffix = "KB"
    elif exponent in range(20, 30):
        value = bytes / 1024**2
        suffix = "MB"
    elif exponent in range(30, 40):
        value = bytes / 1024**3
        suffix = "GB"
    else:
        value = bytes / 1024**4
        suffix = "TB"
    # Add a new case when the first machine with petabyte RAM
    # hits the market.

    size_string = "{0:.{1}f} {2}".format(value, precision, suffix)
    return size_string

def human_to_bytes(value):
    """ Converts a data amount with a unit suffix to bytes, like 2K to 2048 """

    from re import match as re_match

    res = re_match(r'^\s*(\d+(?:\.\d+)?)\s*([a-zA-Z]+)\s*$', value)

    if not res:
        raise ValueError(f"'{value}' is not a valid data amount")
    else:
        amount = float(res.group(1))
        unit = res.group(2).lower()

        if unit == 'b':
            res = amount
        elif (unit == 'k') or (unit == 'kb'):
            res = amount * 1024
        elif (unit == 'm') or (unit == 'mb'):
            res = amount * 1024**2
        elif (unit == 'g') or (unit == 'gb'):
            res = amount * 1024**3
        elif (unit == 't') or (unit == 'tb'):
            res = amount * 1024**4
        else:
            raise ValueError(f"Unsupported data unit '{unit}'")

    # There cannot be fractional bytes, so we convert them to integer.
    # However, truncating causes problems with conversion back to human unit,
    # so we round instead -- that seems to work well enough.
    return round(res)

def mac_to_eui64(mac, prefix=None):
    """
    Convert a MAC address to a EUI64 address or, with prefix provided, a full
    IPv6 address.
    Thankfully copied from https://gist.github.com/wido/f5e32576bb57b5cc6f934e177a37a0d3
    """
    import re
    from ipaddress import ip_network
    # http://tools.ietf.org/html/rfc4291#section-2.5.1
    eui64 = re.sub(r'[.:-]', '', mac).lower()
    eui64 = eui64[0:6] + 'fffe' + eui64[6:]
    eui64 = hex(int(eui64[0:2], 16) ^ 2)[2:].zfill(2) + eui64[2:]

    if prefix is None:
        return ':'.join(re.findall(r'.{4}', eui64))
    else:
        try:
            net = ip_network(prefix, strict=False)
            euil = int('0x{0}'.format(eui64), 16)
            return str(net[euil])
        except:  # pylint: disable=bare-except
            return


def convert_data(data) -> dict | list | tuple | str | int | float | bool | None:
    """Filter and convert multiple types of data to types usable in CLI/API

    WARNING: Must not be used for anything except formatting output for API or CLI

    On the output allowed everything supported in JSON.

    Args:
        data (Any): input data

    Returns:
        dict | list | tuple | str | int | float | bool | None: converted data
    """
    from base64 import b64encode

    # return original data for types which do not require conversion
    if isinstance(data, str | int | float | bool | None):
        return data

    if isinstance(data, list):
        list_tmp = []
        for item in data:
            list_tmp.append(convert_data(item))
        return list_tmp

    if isinstance(data, tuple):
        list_tmp = list(data)
        tuple_tmp = tuple(convert_data(list_tmp))
        return tuple_tmp

    if isinstance(data, bytes | bytearray):
        try:
            return data.decode()
        except UnicodeDecodeError:
            return b64encode(data).decode()

    if isinstance(data, set | frozenset):
        list_tmp = convert_data(list(data))
        return list_tmp

    if isinstance(data, dict):
        dict_tmp = {}
        for key, value in data.items():
            dict_tmp[key] = convert_data(value)
        return dict_tmp

    # do not return anything for other types
    # which cannot be converted to JSON
    # for example: complex | range | memoryview
    return
