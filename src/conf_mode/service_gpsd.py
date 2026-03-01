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
import ast
import os
import re

from sys import exit
from vyos.config import Config
from vyos.template import render
from vyos.utils.process import call
from vyos import ConfigError
from vyos import airbag

SERVICE_NAMES = [ "gpsd.service", "gpsd.socket" ]

CONFIG_FILE = "/run/gpsd/default"
CONFIG_TEMPLATE_FILE = 'gpsd/default.j2'
GPSD_ETC_FILE = "/etc/default/gpsd"
NOTICE = "# This file is not used by VyOS. Instead, please check the contents of /run/gpsd/default\n"
SOCKET_FILE = "/lib/systemd/system/gpsd.socket"
SOCKET_TEMPLATE_FILE = 'gpsd/gpsd.socket.j2'

FLAG_MAP = {
    'bad_time': ['bad-time'],
    'disable_usb_auto': ['disable-usb-auto'],
    'listen_any': ['listen-any'],
    'no_wait': ['no-wait'],
    'read_only': ['read-only'],
}

airbag.enable()

allowed_speeds = {4800, 9600, 19200, 38400, 57600, 115200, 230400, 460800, 921600}

def normalise_source(config):
    """
    Adds config['source_list'] as a proper list of strings
    suitable for Jinja join().
    """
    source = config.get('source')

    if source is None:
        config['source_list'] = []
    elif isinstance(source, list):
        config['source_list'] = source
    elif isinstance(source, str):
        try:
            parsed = ast.literal_eval(source)
            config['source_list'] = parsed if isinstance(parsed, list) else []
        except (ValueError, SyntaxError):
            config['source_list'] = []
    else:
        config['source_list'] = []

    return config

def replace_gpsd_default():
    # Remove existing file or symlink if it exists
    try:
        os.unlink(GPSD_ETC_FILE)
    except FileNotFoundError:
        pass
    except IsADirectoryError:
        raise RuntimeError(f"{GPSD_ETC_FILE} is a directory, refusing to overwrite")

    # Ensure parent directory exists
    parent_dir = os.path.dirname(GPSD_ETC_FILE)
    os.makedirs(parent_dir, exist_ok=True)

    # Write the replacement notice
    with open(GPSD_ETC_FILE, "w", encoding="utf-8") as f:
        f.write(NOTICE)

    # Set permissions
    os.chmod(GPSD_ETC_FILE, 0o644)


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()

    base = ['service', 'gpsd']

    # If node doesn't exist in candidate config, we're deleting it
    if not conf.exists(base):
        return None

    gpsd = conf.get_config_dict(
        base,
        key_mangling=('-', '_'),
        no_tag_node_value_mangle=True,
        get_first_key=True,
        with_recursive_defaults=True,
    )

    normalise_source(gpsd)

    return gpsd

def verify(gpsd):
    # bail out early - looks like removal from running config
    if not gpsd or 'disable' in gpsd:
        return None

    # Make sure debug is a valid number, if set
    if 'debug' in gpsd:
        try:
            debug = int(gpsd['debug'])
        except (TypeError, ValueError):
            raise ConfigError("Debug level must be an integer")

        if not 0 <= debug <= 5:
            raise ConfigError("Debug level must be between 0 and 5 inclusive")

    # If the user has overridden framing it must be in a format gpsd is expecting
    if 'framing' in gpsd and not re.fullmatch(r'[78][ENO][012]', gpsd['framing']):
        raise ConfigError("Framing must match the pattern [78][ENO][012]")

    # Speed can be only one of a few pre-defined options
    if 'speed' in gpsd:
        try:
            speed = int(gpsd['speed'])
        except (TypeError, ValueError):
            raise ConfigError("speed must be an integer")

        if speed not in allowed_speeds:
            allowed_str = ", ".join(str(v) for v in sorted(allowed_speeds))
            raise ConfigError(f"speed must be one of: {allowed_str}")

    # If GPSD is enabled we need at least one source
    if 'source' not in gpsd or len(gpsd['source']) < 1:
        raise ConfigError(
            'No GPSD sources configured.\n'
            'At least one GPSD source must be configured, e.g. /dev/ttyS0'
        )

    # Sources must exist and be openable files not directories
    for source in gpsd['source']:
        if source.startswith('/'):
            if not os.path.exists(source):
                raise ConfigError(f"Source path does not exist: {source}")
            if os.path.isdir(source):
                raise ConfigError(
                    f"Source path must not be a directory: {source}")

    return None


def generate(gpsd):
    # bail out early - looks like removal from running config
    if not gpsd or 'disable' in gpsd:
        return None

    replace_gpsd_default()

    # Write out config to where systemctl is expecting it to be
    render(
        CONFIG_FILE,
        CONFIG_TEMPLATE_FILE,
        gpsd
    )

    # This is a separate file for systemctl detailing which sockets to listen to
    render(
        SOCKET_FILE,
        SOCKET_TEMPLATE_FILE,
        gpsd
    )

    return None


def apply(gpsd):
    # bail out early - looks like removal from running config
    # Stopping/Disabling the service is idempotent and low overhead so it's
    # done every commit regardless
    if not gpsd or 'disable' in gpsd:
        for service in SERVICE_NAMES:
            call(f'systemctl stop {service}')
            call(f'systemctl disable {service}')

        return None

    # Any change to the config requires a restart of GPSD to take
    #
    # Restart is the same as start if the service is stopped so no separate
    # logic path implemented for this case
    for service in SERVICE_NAMES:
        call(f'systemctl enable {service}')
        call(f'systemctl restart {service}')

    return None


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
