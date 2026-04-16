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
                  level: int = logging.INFO):
    """Convenience helper used by every WWAN module.

    Returns a configured ``logging.Logger`` with a syslog handler
    (if ``/dev/log`` is available) and a console handler.
    """
    formatter = WwanSyslogFormatter(app_name)

    try:
        facility_num = WwanSyslogFormatter.FACILITY_MAP.get(app_name, 16)
        syslog_handler = logging.handlers.SysLogHandler(
            address='/dev/log',
            facility=facility_num,
        )
        syslog_handler.setFormatter(formatter)
        use_syslog = True
    except (OSError, IOError):
        use_syslog = False

    console_formatter = logging.Formatter(
        f'%(asctime)s {app_name}[%(process)d]: %(levelname)s: %(message)s'
    )
    console_handler = logging.StreamHandler()
    console_handler.setFormatter(console_formatter)

    lgr = logging.getLogger(logger_name)
    lgr.setLevel(level)
    if use_syslog:
        lgr.addHandler(syslog_handler)
    lgr.addHandler(console_handler)
    lgr.propagate = False

    return lgr
