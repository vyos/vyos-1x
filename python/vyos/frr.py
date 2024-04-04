# Copyright 2020-2024 VyOS maintainers and contributors <maintainers@vyos.io>
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

from vyos import ConfigError
from vyos.utils.process import cmd
from vyos.utils.process import popen
from vyos.utils.process import STDOUT

import logging
from logging.handlers import SysLogHandler
import os
import sys

LOG = logging.getLogger(__name__)
DEBUG = False

ch = SysLogHandler(address='/dev/log')
ch2 = logging.StreamHandler(stream=sys.stdout)
LOG.addHandler(ch)
LOG.addHandler(ch2)

_frr_daemons = ['zebra', 'staticd', 'bgpd', 'ospfd', 'ospf6d', 'ripd', 'ripngd',
                'isisd', 'pimd', 'pim6d', 'ldpd', 'eigrpd', 'babeld', 'bfdd']

path_vtysh = '/usr/bin/vtysh'
path_frr_reload = '/usr/lib/frr/frr-reload.py'
path_config = '/run/frr'

default_add_before = r'(ip prefix-list .*|route-map .*|line vty|end)'


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

def init_debugging():
    global DEBUG

    DEBUG = os.path.exists('/tmp/vyos.frr.debug')
    if DEBUG:
        LOG.setLevel(logging.DEBUG)

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

    output, code = popen(cmd, stderr=STDOUT)
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
    output, code = popen(f"{path_vtysh} -m -f -", stderr=STDOUT, input=config)

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

    LOG.debug(f'reload_configuration: Reloading config using temporary file: {f.name}')
    cmd = f'{path_frr_reload} --reload'
    if daemon:
        cmd += f' --daemon {daemon}'

    if DEBUG:
        cmd += f' --debug --stdout'

    cmd += f' {f.name}'

    LOG.debug(f'reload_configuration: Executing command against frr-reload: "{cmd}"')
    output, code = popen(cmd, stderr=STDOUT)
    f.close()

    for i, e in enumerate(output.split('\n')):
        LOG.debug(f'frr-reload output: {i:3} {e}')

    if code == 1:
        raise ConfigError(output)
    elif code:
        raise OSError(code, output)

    return output


def save_configuration():
    """ T3217: Save FRR configuration to /run/frr/config/frr.conf """
    return cmd(f'{path_vtysh} -n -w')


def execute(command):
    """ Run commands inside vtysh
    command:  str containing commands to execute inside a vtysh session
    """
    if not isinstance(command, str):
        raise ValueError(f'command needs to be a string: {repr(command)}')

    cmd = f"{path_vtysh} -c '{command}'"

    output, code = popen(cmd, stderr=STDOUT)
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

    output, code = popen(cmd, stderr=STDOUT)
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
    # DEPRECATED, this is replaced by a new implementation
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
    # DEPRECATED, this is replaced by a new implementation
    return _replace_section(config, replacement, replace_re=rf'^{from_re}$.*?^{to_re}$', before_re=rf'^({before_re})$')


def remove_section(config, from_re, to_re='!'):
    # DEPRECATED, this is replaced by a new implementation
    return _replace_section(config, '', replace_re=rf'^{from_re}$.*?^{to_re}$', before_re=None)


def _find_first_block(config, start_pattern, stop_pattern, start_at=0):
    '''Find start and stop line numbers for a config block
    config:        (list) A list conaining the configuration that is searched
    start_pattern: (raw-str) The pattern searched for a a start of block tag
    stop_pattern:  (raw-str) The pattern searched for to signify the end of the block
    start_at:      (int) The index to start searching at in the <config>

    Returns:
        None: No complete block could be found
        set(int, int): A complete block found between the line numbers returned in the set

    The object <config> is searched from the start for the regex <start_pattern> until the first match is found.
    On a successful match it continues the search for the regex <stop_pattern> until it is found.
    After a successful run a set is returned containing the start and stop line numbers.
    '''
    LOG.debug(f'_find_first_block: find start={repr(start_pattern)} stop={repr(stop_pattern)} start_at={start_at}')
    _start = None
    for i, element in enumerate(config[start_at:], start=start_at):
        # LOG.debug(f'_find_first_block: running line {i:3} "{element}"')
        if not _start:
            if not re.match(start_pattern, element):
                LOG.debug(f'_find_first_block: no match     {i:3} "{element}"')
                continue
            _start = i
            LOG.debug(f'_find_first_block: Found start  {i:3} "{element}"')
            continue

        if not re.match(stop_pattern, element):
            LOG.debug(f'_find_first_block: no match     {i:3} "{element}"')
            continue

        LOG.debug(f'_find_first_block: Found stop   {i:3} "{element}"')
        return (_start, i)

    LOG.debug('_find_first_block: exit start={repr(start_pattern)} stop={repr(stop_pattern)} start_at={start_at}')
    return None


def _find_first_element(config, pattern, start_at=0):
    '''Find the first element that matches the current pattern in config
    config:        (list) A list containing the configuration that is searched
    start_pattern: (raw-str) The pattern searched for
    start_at:      (int) The index to start searching at in the <config>

    return:   Line index of the line containing the searched pattern

    TODO: for now it returns -1 on a no-match because 0 also returns as False
    TODO: that means that we can not use False matching to tell if its
    '''
    LOG.debug(f'_find_first_element: find start="{pattern}" start_at={start_at}')
    for i, element in enumerate(config[start_at:], start=0):
        if re.match(pattern + '$', element):
            LOG.debug(f'_find_first_element: Found stop {i:3} "{element}"')
            return i
        LOG.debug(f'_find_first_element: no match   {i:3} "{element}"')
    LOG.debug(f'_find_first_element: Did not find any match, exiting')
    return -1


def _find_elements(config, pattern, start_at=0):
    '''Find all instances of pattern and return a list containing all element indexes
    config:        (list) A list containing the configuration that is searched
    start_pattern: (raw-str) The pattern searched for
    start_at:      (int) The index to start searching at in the <config>

    return:    A list of line indexes containing the searched pattern
    TODO: refactor this to return a generator instead
    '''
    return [i for i, element in enumerate(config[start_at:], start=0) if re.match(pattern + '$', element)]


class FRRConfig:
    '''Main FRR Configuration manipulation object
    Using this object the user could load, manipulate and commit the configuration to FRR
    '''
    def __init__(self, config=[]):
        self.imported_config = ''

        if isinstance(config, list):
            self.config = config.copy()
            self.original_config = config.copy()
        elif isinstance(config, str):
            self.config = config.split('\n')
            self.original_config = self.config.copy()
        else:
            raise ValueError(
                'The config element needs to be a string or list type object')

        if config:
            LOG.debug(f'__init__: frr library initiated with initial config')
            for i, e in enumerate(self.config):
                LOG.debug(f'__init__: initial              {i:3} {e}')

    def load_configuration(self, daemon=None):
        '''Load the running configuration from FRR into the config object
        daemon: str with name of the FRR Daemon to load configuration from or
                None to load the consolidated config

        Using this overwrites the current loaded config objects and replaces the original loaded config
        '''
        init_debugging()

        self.imported_config = get_configuration(daemon=daemon)
        if daemon:
            LOG.debug(f'load_configuration: Configuration loaded from FRR daemon {daemon}')
        else:
            LOG.debug(f'load_configuration: Configuration loaded from FRR integrated config')

        self.original_config = self.imported_config.split('\n')
        self.config = self.original_config.copy()

        for i, e in enumerate(self.imported_config.split('\n')):
            LOG.debug(f'load_configuration:  loaded    {i:3} {e}')
        return

    def test_configuration(self):
        '''Test the current configuration against FRR
        This will exception if FRR failes to load the current configuration object
        '''
        LOG.debug('test_configation: Testing configuration')
        mark_configuration('\n'.join(self.config))

    def commit_configuration(self, daemon=None):
        '''
        Commit the current configuration to FRR daemon: str with name of the
        FRR daemon to commit to or None to use the consolidated config.

        Configuration is automatically saved after apply
        '''
        LOG.debug('commit_configuration:  Commiting configuration')
        for i, e in enumerate(self.config):
            LOG.debug(f'commit_configuration: new_config {i:3} {e}')

        # https://github.com/FRRouting/frr/issues/10132
        # https://github.com/FRRouting/frr/issues/10133
        count = 0
        count_max = 5
        emsg = ''
        while count < count_max:
            count += 1
            try:
                reload_configuration('\n'.join(self.config), daemon=daemon)
                break
            except ConfigError as e:
                emsg = str(e)
            except:
                # we just need to re-try the commit of the configuration
                # for the listed FRR issues above
                pass
        if count >= count_max:
            if emsg:
                raise ConfigError(emsg)
            raise ConfigurationNotValid(f'Config commit retry counter ({count_max}) exceeded for {daemon} daemon!')

        # Save configuration to /run/frr/config/frr.conf
        save_configuration()


    def modify_section(self, start_pattern, replacement='!', stop_pattern=r'\S+', remove_stop_mark=False, count=0):
        if isinstance(replacement, str):
            replacement = replacement.split('\n')
        elif not isinstance(replacement, list):
            return ValueError("The replacement element needs to be a string or list type object")
        LOG.debug(f'modify_section: starting search for {repr(start_pattern)} until {repr(stop_pattern)}')

        _count = 0
        _next_start = 0
        while True:
            if count and count <= _count:
                # Break out of the loop after specified amount of matches
                LOG.debug(f'modify_section: reached limit ({_count}), exiting loop at line {_next_start}')
                break
            # While searching, always assume that the user wants to search for the exact pattern he entered
            # To be more specific the user needs a override, eg. a "pattern.*"
            _w = _find_first_block(
                self.config, start_pattern+'$', stop_pattern, start_at=_next_start)
            if not _w:
                # Reached the end, no more elements to remove
                LOG.debug(f'modify_section: No more config sections found, exiting')
                break
            start_element, end_element = _w
            LOG.debug(f'modify_section:   found match between {start_element} and {end_element}')
            for i, e in enumerate(self.config[start_element:end_element+1 if remove_stop_mark else end_element],
                                  start=start_element):
                LOG.debug(f'modify_section:   remove       {i:3} {e}')
            del self.config[start_element:end_element +
                            1 if remove_stop_mark else end_element]
            if replacement:
                # Append the replacement config at the current position
                for i, e in enumerate(replacement, start=start_element):
                    LOG.debug(f'modify_section:   add          {i:3} {e}')
                self.config[start_element:start_element] = replacement
            _count += 1
            _next_start = start_element + len(replacement)

        return _count

    def add_before(self, before_pattern, addition):
        '''Add config block before this element in the configuration'''
        if isinstance(addition, str):
            addition = addition.split('\n')
        elif not isinstance(addition, list):
            return ValueError("The replacement element needs to be a string or list type object")

        start = _find_first_element(self.config, before_pattern)
        if start < 0:
            return False
        for i, e in enumerate(addition, start=start):
            LOG.debug(f'add_before:   add          {i:3} {e}')
        self.config[start:start] = addition
        return True

    def __str__(self):
        return '\n'.join(self.config)

    def __repr__(self):
        return f'frr({repr(str(self))})'
