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

# import logging and related modules
import logging
from logging.handlers import SysLogHandler, RotatingFileHandler
from sys import stderr

# create logger
logger = logging.getLogger(__name__)
# define logs format
logs_format = logging.Formatter('%(filename)s: %(message)s')

# add default handler - syslog
logs_handler_syslog = SysLogHandler('/dev/log')
logs_handler_syslog.setFormatter(logs_format)
logger.addHandler(logs_handler_syslog)
# set default level to INFO
logger.setLevel(logging.INFO)


class logger_opts:
    # save all what may be used in logging config
    CRITICAL = logging.CRITICAL
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    INFO = logging.INFO
    DEBUG = logging.DEBUG
    NOTSET = logging.NOTSET
    Formatter = logging.Formatter

    # additional handler - stream
    def handler_stream(stream=stderr):
        # create stream handler
        handler_stream = logging.StreamHandler(stream)
        logs_format_stream = logging.Formatter('%(asctime)s (%(filename)s) %(levelname)s: %(message)s')
        handler_stream.setFormatter(logs_format_stream)
        # return handler
        return handler_stream

    # additional handler - file
    def handler_file(file, **kwargs):
        # get options, if they are presented
        maxBytesValue = kwargs.get('maxBytes', 1048576)
        backupCountValue = kwargs.get('backupCount', 3)
        # create handler and set format
        handler_file = RotatingFileHandler(file, maxBytes=maxBytesValue, backupCount=backupCountValue)
        logs_format_file = logging.Formatter('%(asctime)s (%(filename)s) %(levelname)s: %(message)s')
        handler_file.setFormatter(logs_format_file)
        # return handler
        return handler_file
