# Copyright 2020 VyOS maintainers and contributors <maintainers@vyos.io>
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

r"""
A Library for interracting with the FRR daemon suite.
It supports simple configuration manipulation and loading using the official tools
supplied with FRR (vtysh and frr-reload)

All configuration management and manipulation is done using strings and regex.


Example Usage
#####

# Reading configuration from frr:
```
>>> original_config = get_configuration()
>>> repr(original_config)
'!\nfrr version 7.3.1\nfrr defaults traditional\nhostname debian\n......
```


# Modify a configuration section:
```
>>> new_bgp_section = 'router bgp 65000\n neighbor 192.0.2.1 remote-as 65000\n'
>>> modified_config = replace_section(original_config, new_bgp_section, replace_re=r'router bgp \d+')
>>> repr(modified_config)
'............router bgp 65000\n neighbor 192.0.2.1 remote-as 65000\n...........'
```

Remove a configuration section:
```
>>> modified_config = remove_section(original_config, r'router ospf')
```

Test the new configuration:
```
>>> try:
>>>     mark_configuration(modified configuration)
>>> except ConfigurationNotValid as e:
>>>     print('resulting configuration is not valid')
>>>     sys.exit(1)
```

Apply the new configuration:
```
>>> try:
>>>     replace_configuration(modified_config)
>>> except CommitError as e:
>>>     print('Exception while commiting the supplied configuration')
>>>     print(e)
>>>     exit(1)
```
"""

import tempfile
import re
from vyos import util

_frr_daemons = ['zebra', 'bgpd', 'fabricd', 'isisd', 'ospf6d', 'ospfd', 'pbrd',
                'pimd', 'ripd', 'ripngd', 'sharpd', 'staticd', 'vrrpd', 'ldpd']

path_vtysh = '/usr/bin/vtysh'
path_frr_reload = '/usr/lib/frr/frr-reload.py'


class FrrError(Exception):
    pass


class ConfigurationNotValid(FrrError):
    """
    The configuratioin supplied to vtysh is not valid
    """
    pass


class CommitError(FrrError):
    """
    Commiting the supplied configuration failed to commit by a unknown reason
    see commit error and/or run mark_configuration on the specified configuration
    to se error generated

    used by: reload_configuration()
    """
    pass


class ConfigSectionNotFound(FrrError):
    """
    Removal of configuration failed because it is not existing in the supplied configuration
    """
    pass


def get_configuration(daemon=None, marked=False):
    """ Get current running FRR configuration
    daemon:  Collect only configuration for the specified FRR daemon,
             supplying daemon=None retrieves the complete configuration
    marked:  Mark the configuration with "end" tags

    return:  string containing the running configuration from frr

    """
    if daemon and daemon not in _frr_daemons:
        raise ValueError(f'The specified daemon type is not supported {repr(daemon)}')

    cmd = f"{path_vtysh} -c 'show run'"
    if daemon:
        cmd += f' -d {daemon}'

    output, code = util.popen(cmd, stderr=util.STDOUT)
    if code:
        raise OSError(code, output)

    config = output.replace('\r', '')
    # Remove first header lines from FRR config
    config = config.split("\n", 3)[-1]
    # Mark the configuration with end tags
    if marked:
        config = mark_configuration(config)

    return config


def mark_configuration(config):
    """ Add end marks and Test the configuration for syntax faults
    If the configuration is valid a marked version of the configuration is returned,
    or else it failes with a ConfigurationNotValid Exception

    config:  The configuration string to mark/test
    return:  The marked configuration from FRR
    """
    output, code = util.popen(f"{path_vtysh} -m -f -", stderr=util.STDOUT, input=config)

    if code == 2:
        raise ConfigurationNotValid(str(output))
    elif code:
        raise OSError(code, output)

    config = output.replace('\r', '')
    return config


def reload_configuration(config, daemon=None):
    """ Execute frr-reload with the new configuration
    This will try to reapply the supplied configuration inside FRR.
    The configuration needs to be a complete configuration from the integrated config or
    from a daemon.

    config:  The configuration to apply
    daemon:  Apply the conigutaion to the specified FRR daemon,
             supplying daemon=None applies to the integrated configuration
    return:  None
    """
    if daemon and daemon not in _frr_daemons:
        raise ValueError(f'The specified daemon type is not supported {repr(daemon)}')

    f = tempfile.NamedTemporaryFile('w')
    f.write(config)
    f.flush()

    cmd = f'{path_frr_reload} --reload'
    if daemon:
        cmd += f' --daemon {daemon}'
    cmd += f' {f.name}'

    output, code = util.popen(cmd, stderr=util.STDOUT)
    f.close()
    if code == 1:
        raise CommitError(f'Configuration FRR failed while commiting code: {repr(output)}')
    elif code:
        raise OSError(code, output)

    return output


def execute(command):
    """ Run commands inside vtysh
    command:  str containing commands to execute inside a vtysh session
    """
    if not isinstance(command, str):
        raise ValueError(f'command needs to be a string: {repr(command)}')

    cmd = f"{path_vtysh} -c '{command}'"

    output, code = util.popen(cmd, stderr=util.STDOUT)
    if code:
        raise OSError(code, output)

    config = output.replace('\r', '')
    return config


def configure(lines, daemon=False):
    """ run commands inside config mode vtysh
    lines:  list or str conaining commands to execute inside a configure session
            only one command executed on each configure()
            Executing commands inside a subcontext uses the list to describe the context
            ex: ['router bgp 6500', 'neighbor 192.0.2.1 remote-as 65000']
    return: None
    """
    if isinstance(lines, str):
        lines = [lines]
    elif not isinstance(lines, list):
        raise ValueError('lines needs to be string or list of commands')

    if daemon and daemon not in _frr_daemons:
        raise ValueError(f'The specified daemon type is not supported {repr(daemon)}')

    cmd = f'{path_vtysh}'
    if daemon:
        cmd += f' -d {daemon}'

    cmd += " -c 'configure terminal'"
    for x in lines:
        cmd += f" -c '{x}'"

    output, code = util.popen(cmd, stderr=util.STDOUT)
    if code == 1:
        raise ConfigurationNotValid(f'Configuration FRR failed: {repr(output)}')
    elif code:
        raise OSError(code, output)

    config = output.replace('\r', '')
    return config


def _replace_section(config, replacement, replace_re, before_re):
    r"""Replace a section of FRR config
    config:      full original configuration
    replacement: replacement configuration section
    replace_re:  The regex to replace
                 example: ^router bgp \d+$.?*^!$
                 this will replace everything between ^router bgp X$ and ^!$
    before_re:   When replace_re is not existant, the config will be added before this tag
                 example: ^line vty$

    return:      modified configuration as a text file
    """
    # Check if block is configured, remove the existing instance else add a new one
    if re.findall(replace_re, config, flags=re.MULTILINE | re.DOTALL):
        # Section is in the configration, replace it
        return re.sub(replace_re, replacement, config, count=1,
                      flags=re.MULTILINE | re.DOTALL)
    if before_re:
        if not re.findall(before_re, config, flags=re.MULTILINE | re.DOTALL):
            raise ConfigSectionNotFound(f"Config section {before_re} not found in config")

        # If no section is in the configuration, add it before the line vty line
        return re.sub(before_re, rf'{replacement}\n\g<1>', config, count=1,
                      flags=re.MULTILINE | re.DOTALL)

    raise ConfigSectionNotFound(f"Config section {replacement} not found in config")


def replace_section(config, replacement, from_re, to_re=r'!', before_re=r'line vty'):
    r"""Replace a section of FRR config
    config:      full original configuration
    replacement: replacement configuration section
    from_re:     Regex for the start of section matching
                 example: 'router bgp \d+'
    to_re:       Regex for stop of section matching
                 default: '!'
                 example: '!'  or  'end'
    before_re:   When from_re/to_re  does not return a match, the config will
                 be added before this tag
                 default: ^line vty$

    startline and endline tags will be automatically added to the resulting from_re/to_re and before_re regex'es
    """
    return _replace_section(config, replacement, replace_re=rf'^{from_re}$.*?^{to_re}$', before_re=rf'^{before_re}$')


def remove_section(config, from_re, to_re='!'):
    return _replace_section(config, '', replace_re=rf'^{from_re}$.*?^{to_re}$', before_re=None)
