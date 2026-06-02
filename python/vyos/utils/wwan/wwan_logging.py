# Copyright (C) 2024-2026 Perle Systems Limited
# SPDX-License-Identifier: GPL-2.0-or-later
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

"""
Shared syslog logging for WWAN package.

Provides a WwanSyslogFormatter that produces RFC 3164-compatible messages
for the local /dev/log Unix socket, and a setup_logging() helper used by
every WWAN module.

RFC 3164 is the correct choice for /dev/log because:
- systemd-journald and rsyslog both expect RFC 3164 on local sockets
- Python's SysLogHandler already prepends <PRI>; a formatter that also
  emits <PRI> (as RFC 5424 requires) causes double-encoding
- Structured data fields are silently discarded by journald
"""

import logging
import logging.handlers


VALID_LOG_SINKS = {'both', 'journal', 'syslog'}
_DEFAULT_LOG_SINK = 'both'
_LOGGER_REGISTRY = {}


def _normalize_sink(sink: str | None) -> str:
    if sink is None:
        return _DEFAULT_LOG_SINK
    sink_val = str(sink).strip().lower()
    if sink_val not in VALID_LOG_SINKS:
        return _DEFAULT_LOG_SINK
    return sink_val


class WwanSyslogFormatter(logging.Formatter):
    """RFC 3164 syslog formatter for local /dev/log.

    Produces messages like::

        wwan-fsm[12345]: INFO: Modem connected

    SysLogHandler adds the <PRI> header; rsyslog/journald adds the
    timestamp and hostname.
    """

    FACILITY_MAP = {
        'wwan-manager': 16,   # local0
        'wwan-service': 17,   # local1
        'wwan-config':  18,   # local2
        'wwan-fsm':     19,   # local3
    }

    def __init__(self, app_name: str = "wwan"):
        super().__init__()
        self.app_name = app_name

    def format(self, record):
        return (
            f"{self.app_name}[{record.process}]: "
            f"{record.levelname}: {record.getMessage()}"
        )


def setup_logging(logger_name: str,
                  app_name: str,
                  level: int = logging.INFO,
                  sink: str | None = None):
    """Convenience helper used by every WWAN module.

    Returns a configured ``logging.Logger`` with a syslog handler
    (if ``/dev/log`` is available) and a console handler.
    """
    sink_mode = _normalize_sink(sink)
    formatter = WwanSyslogFormatter(app_name)
    lgr = logging.getLogger(logger_name)
    lgr.setLevel(level)

    # Remove existing WWAN-managed handlers to prevent duplicates.
    for handler in list(lgr.handlers):
        if getattr(handler, '_wwan_managed', False):
            lgr.removeHandler(handler)

    if sink_mode in ('both', 'syslog'):
        try:
            facility_num = WwanSyslogFormatter.FACILITY_MAP.get(app_name, 16)
            syslog_handler = logging.handlers.SysLogHandler(
                address='/dev/log',
                facility=facility_num,
            )
            syslog_handler.setFormatter(formatter)
            syslog_handler._wwan_managed = True
            lgr.addHandler(syslog_handler)
        except (OSError, IOError):
            # Graceful fallback: continue with remaining sinks.
            pass

    if sink_mode in ('both', 'journal'):
        console_formatter = logging.Formatter(
            f'%(asctime)s {app_name}[%(process)d]: %(levelname)s: %(message)s'
        )
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(console_formatter)
        console_handler._wwan_managed = True
        lgr.addHandler(console_handler)

    lgr.propagate = False
    _LOGGER_REGISTRY[logger_name] = app_name

    return lgr


def reconfigure_logging(sink: str | None = None,
                        level: int | None = None):
    """Reconfigure all previously created WWAN loggers at runtime."""
    sink_mode = _normalize_sink(sink)
    for logger_name, app_name in _LOGGER_REGISTRY.items():
        lgr = logging.getLogger(logger_name)
        effective_level = lgr.level if level is None else level
        setup_logging(logger_name, app_name, effective_level, sink_mode)

    return sink_mode
