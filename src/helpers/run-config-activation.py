#!/usr/bin/env python3
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

import re
import logging
from pathlib import Path
from argparse import ArgumentParser

from vyos.compose_config import ComposeConfig
from vyos.compose_config import ComposeConfigError
from vyos.defaults import directories

parser = ArgumentParser()
parser.add_argument('config_file', type=str,
                    help="configuration file to modify with system-specific settings")
parser.add_argument('--test-script', type=str,
                    help="test effect of named script")

args = parser.parse_args()

checkpoint_file = '/run/vyos-activate-checkpoint'
log_file = Path(directories['config']).joinpath('vyos-activate.log')

logger = logging.getLogger(__name__)
fh = logging.FileHandler(log_file)
formatter = logging.Formatter('%(message)s')
fh.setFormatter(formatter)
logger.addHandler(fh)

if 'vyos-activate-debug' in Path('/proc/cmdline').read_text():
    print(f'\nactivate-debug enabled: file {checkpoint_file}_* on error')
    debug = checkpoint_file
    logger.setLevel(logging.DEBUG)
else:
    debug = None
    logger.setLevel(logging.INFO)

def sort_key(s: Path):
    s = s.stem
    pre, rem = re.match(r'(\d*)(?:-)?(.+)', s).groups()
    return int(pre or 0), rem

def file_ext(file_name: str) -> str:
    """Return an identifier from file name for checkpoint file extension.
    """
    return Path(file_name).stem

script_dir = Path(directories['activate'])

if args.test_script:
    script_list = [script_dir.joinpath(args.test_script)]
else:
    script_list = sorted(script_dir.glob('*.py'), key=sort_key)

config_file = args.config_file
config_str = Path(config_file).read_text()

compose = ComposeConfig(config_str, checkpoint_file=debug)

for file in script_list:
    file = file.as_posix()
    logger.info(f'calling {file}')
    try:
        compose.apply_file(file, func_name='activate')
    except ComposeConfigError as e:
        if debug:
            compose.write(f'{compose.checkpoint_file}_{file_ext(file)}')
        logger.error(f'config-activation error in {file}: {e}')

compose.write(config_file, with_version=True)
