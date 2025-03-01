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

def begin(*args):
    """
    Evaluate arguments in order and return the result of the *last* argument.
    For combining multiple expressions in one statement. Useful for lambdas.
    """
    return args[-1]

def begin0(*args):
    """
    Evaluate arguments in order and return the result of the *first* argument.
    For combining multiple expressions in one statement. Useful for lambdas.
    """
    return args[0]

def install_into_config(conf, config_paths, override_prompt=True):
    # Allows op-mode scripts to install values if called from an active config session
    # config_paths: dict of config paths
    # override_prompt: if True, user will be prompted before existing nodes are overwritten
    if not config_paths:
        return None

    from vyos.config import Config
    from vyos.utils.io import ask_yes_no
    from vyos.utils.process import cmd
    if not Config().in_session():
        print('You are not in configure mode, commands to install manually from configure mode:')
        for path in config_paths:
            print(f'set {path}')
        return None

    count = 0
    failed = []

    for path in config_paths:
        if override_prompt and conf.exists(path) and not conf.is_multi(path):
            if not ask_yes_no(f'Config node "{node}" already exists. Do you want to overwrite it?'):
                continue

        try:
            cmd(f'/opt/vyatta/sbin/my_set {path}')
            count += 1
        except:
            failed.append(path)

    if failed:
        print(f'Failed to install {len(failed)} value(s). Commands to manually install:')
        for path in failed:
            print(f'set {path}')

    if count > 0:
        print(f'{count} value(s) installed. Use "compare" to see the pending changes, and "commit" to apply.')
