#!/usr/bin/env python3
#
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.


import sys
import logging

from pathlib import Path
from argparse import ArgumentParser

from vyos.compose_config import ComposeConfig
from vyos.compose_config import ComposeConfigError
from vyos.utils.activate import refresh_activation_list
from vyos.utils.activate import get_activation_scripts
from vyos.utils.activate import get_activation
from vyos.utils.activate import set_activation
from vyos.utils.activate import is_active
from vyos.utils.system import load_as_module
from vyos.utils.func import FalseCallable
from vyos.utils.kernel import get_kernel_boot_arg
from vyos.defaults import directories
from vyos.defaults import activation_list


parser = ArgumentParser()
parser.add_argument(
    'config_file',
    type=str,
    help='configuration file to modify with system-specific settings',
)
parser.add_argument('--test-script', type=str, help='test effect of named script')

args = parser.parse_args()

checkpoint_file = '/run/vyos-activate-checkpoint'
log_file = Path(directories['config']).joinpath('vyos-activate.log')

logger = logging.getLogger(__name__)
fh = logging.FileHandler(log_file)
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)


if get_kernel_boot_arg('vyos-activate-debug') is not None:
    print(f'\nactivate-debug enabled: file {checkpoint_file}_* on error')
    debug = checkpoint_file
    logger.setLevel(logging.DEBUG)
else:
    debug = None
    logger.setLevel(logging.INFO)


def file_ext(file_name: str) -> str:
    """Return an identifier from file name for checkpoint file extension."""
    return Path(file_name).stem


refresh_activation_list()

if not Path(activation_list).exists():
    logger.error('Missing config activation list!')
    sys.exit(1)

script_dir = Path(directories['activate'])

if args.test_script:
    script_list = [script_dir.joinpath(args.test_script).stem]
else:
    script_list = list(get_activation_scripts())

config_file = args.config_file
config_str = Path(config_file).read_text()

compose = ComposeConfig(config_str, checkpoint_file=debug)

false_call = FalseCallable()

update_config = False
for file in script_list:
    if not is_active(file):
        continue

    logger.info(f'calling {file}')

    mod_name = Path(file).stem.replace('-', '_')
    mod = load_as_module(mod_name, script_dir.joinpath(f'{file}.py').as_posix())

    pre_condition = getattr(mod, 'pre_condition', false_call)
    post_condition = getattr(mod, 'post_condition', false_call)
    activate = getattr(mod, 'activate', false_call)

    if not activate:
        logger.error(f'missing activate function in {file}')
        continue

    if not pre_condition or pre_condition():
        try:
            compose.apply_func(activate)
        except ComposeConfigError as e:
            if debug:
                compose.write(f'{compose.checkpoint_file}_{file_ext(file)}')
            logger.error(f'config-activation error in {file}: {e}')
            update_config = False
            break

        if post_condition:
            post_condition()

        if get_activation(file) == 'once':
            set_activation(file, 'off')

        update_config = True

if update_config:
    compose.write(config_file, with_version=True)
