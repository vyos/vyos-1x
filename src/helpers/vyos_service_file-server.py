#!/usr/bin/env python3
#
# Copyright (C) 2023 VyOS maintainers and contributors
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
#
#

import argparse
import logging
import os
import toml

from functools import partial
from pathlib import Path
from http.server import SimpleHTTPRequestHandler
from http.server import HTTPServer


def file_server(server_directory, bind_address='0.0.0.0', bind_port=8000):
    """Simple file server.

    Args:
        server_directory (str): The directory containing files to be served.
        bind_address (str): The IP address to bind the server to. Defaults to '0.0.0.0'.
        bind_port (int): The port to bind the server to. Defaults to 8000.
    """
    logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)
    logger.name = os.path.basename(__file__)

    logger.info(f'Serving files from: {server_directory}')
    logger.info(f'Binding to: {bind_address}:{bind_port}')

    handler_class = partial(SimpleHTTPRequestHandler, directory=server_directory)

    with HTTPServer((bind_address, bind_port), handler_class) as http_server:
        logger.info(f'Starting file server on http://{bind_address}:{bind_port}')
        try:
            http_server.serve_forever()
        except KeyboardInterrupt:
            logger.info('File server terminated')


if __name__ == "__main__":

    parser = argparse.ArgumentParser()
    parser.add_argument('-c',
                        '--config',
                        action='store',
                        help='Path configuration file',
                        required=True,
                        type=Path)

    args = parser.parse_args()
    config_file = args.config

    # Config in TOML format:
    # $ cat /run/vyos-fileserver.conf
    #   directory = "/tmp"
    #   listen_address = "0.0.0.0"
    #   port = "8000"

    with open(config_file, 'r') as toml_file:
        config = toml.load(toml_file)

    directory = config.get('directory')
    listen_address = config.get('listen_address')
    port = int(config.get('port'))

    # Run file server
    file_server(directory, listen_address, port)
