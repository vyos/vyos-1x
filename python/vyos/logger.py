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

# A wrapper class around logging to make it easier to use

# for a syslog logger:
# from vyos.logger import syslog
# syslog.critical('message')

# for a stderr logger:
# from vyos.logger import stderr
# stderr.critical('message')

# for a custom logger (syslog and file):
# from vyos.logger import getLogger
# combined = getLogger(__name__, syslog=True, stream=sys.stdout, filename='/tmp/test')
# combined.critical('message')

import sys
import logging
import logging.handlers as handlers

TIMED = '%(asctime)s: %(message)s'
SHORT = '%(filename)s: %(message)s'
CLEAR = '%(levelname) %(asctime)s %(filename)s: %(message)s'

_levels = {
    'CRITICAL': logging.CRITICAL,
   	'ERROR': logging.CRITICAL,
   	'WARNING': logging.WARNING,
   	'INFO': logging.INFO,
   	'DEBUG': logging.DEBUG,
   	'NOTSET': logging.NOTSET,
}

# prevent recreation of already created logger
_created = {}

def getLogger(name=None, **kwargs):
	if name in _created:
		if len(kwargs) == 0:
			return _created[name]
		raise ValueError('a logger with the name "{name} already exists')

	logger = logging.getLogger(name)
	logger.setLevel(_levels[kwargs.get('level', 'DEBUG')])

	if 'address' in kwargs or kwargs.get('syslog', False):
		logger.addHandler(_syslog(**kwargs))
	if 'stream' in kwargs:
		logger.addHandler(_stream(**kwargs))
	if 'filename' in kwargs:
		logger.addHandler(_file(**kwargs))

	_created[name] = logger
	return logger


def _syslog(**kwargs):
	formating = kwargs.get('format', SHORT)
	handler = handlers.SysLogHandler(
		address=kwargs.get('address', '/dev/log'),
		facility=kwargs.get('facility', 'syslog'),
	)
	handler.setFormatter(logging.Formatter(formating))
	return handler


def _stream(**kwargs):
	formating = kwargs.get('format', CLEAR)
	handler = logging.StreamHandler(
		stream=kwargs.get('stream', sys.stderr),
	)
	handler.setFormatter(logging.Formatter(formating))
	return handler


def _file(**kwargs):
	formating = kwargs.get('format', CLEAR)
	handler = handlers.RotatingFileHandler(
		filename=kwargs.get('filename', 1048576),
		maxBytes=kwargs.get('maxBytes', 1048576),
		backupCount=kwargs.get('backupCount', 3),
	)
	handler.setFormatter(logging.Formatter(formating))
	return handler


# exported pre-built logger, please keep in mind that the names
# must be unique otherwise the logger are shared

# a logger for stderr
stderr = getLogger(
	'VyOS Syslog',
	format=SHORT,
	stream=sys.stderr,
	address='/dev/log'
)

# a logger to syslog
syslog = getLogger(
	'VyOS StdErr',
	format='%(message)s',
	address='/dev/log'
)


# testing
if __name__ == '__main__':
	# from vyos.logger import getLogger
	formating = '%(asctime)s (%(filename)s) %(levelname)s: %(message)s'

	# syslog logger
	# syslog=True if no 'address' field is provided
	syslog = getLogger(__name__ + '.1', syslog=True, format=formating)
	syslog.info('syslog test')

	# steam logger
	stream = getLogger(__name__ + '.2', stream=sys.stdout, level='ERROR')
	stream.info('steam test')

	# file logger
	filelog = getLogger(__name__ + '.3', filename='/tmp/test')
	filelog.info('file test')

	# create a combined logger
	getLogger('VyOS', syslog=True, stream=sys.stdout, filename='/tmp/test')

	# recover the created logger from name
	combined = getLogger('VyOS')
	combined.info('combined test')
