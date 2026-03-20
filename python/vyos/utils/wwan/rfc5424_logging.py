"""
Shared RFC 5424 syslog formatter for WWAN package.

Provides a base RFC5424Formatter class that all WWAN modules import
instead of each maintaining their own copy.  Subclass and override
``_get_message_id`` / ``_build_structured_data`` when you need
module-specific SNMP categorisation; the core formatting logic is
defined exactly once here.
"""

import logging
import logging.handlers
import socket
from datetime import datetime, timezone


class RFC5424Formatter(logging.Formatter):
    """RFC 5424 compliant syslog formatter for SNMP integration.

    Parameters
    ----------
    app_name : str
        Application name written into every syslog message
        (e.g. ``"wwan-fsm"``, ``"wwan-config"``).
    facility : int
        Syslog facility number (16=local0 … 23=local7).
    """

    # Facility look-up for convenience.  Callers may also pass a raw int.
    FACILITY_MAP = {
        'wwan-manager': 16,   # local0
        'wwan-service': 17,   # local1
        'wwan-config':  18,   # local2
        'wwan-fsm':     19,   # local3
    }

    SEVERITY_MAP = {
        logging.DEBUG:    7,
        logging.INFO:     6,
        logging.WARNING:  4,
        logging.ERROR:    3,
        logging.CRITICAL: 2,
    }

    def __init__(self, app_name: str = "wwan", facility: int = None):
        super().__init__()
        self.app_name = app_name
        self.hostname = socket.gethostname()
        # Resolve facility: explicit int wins, then look-up by name, then 16.
        if facility is not None:
            self.facility = facility
        else:
            self.facility = self.FACILITY_MAP.get(app_name, 16)

    # ------------------------------------------------------------------
    # Core format — identical across all five previous copies
    # ------------------------------------------------------------------

    def format(self, record):
        severity = self.SEVERITY_MAP.get(record.levelno, 6)
        priority = self.facility * 8 + severity

        timestamp = datetime.fromtimestamp(record.created, tz=timezone.utc)
        timestamp_str = timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f')[:-3] + 'Z'

        pid = record.process or '-'
        msgid = self._get_message_id(record)
        structured_data = self._build_structured_data(record)

        return (
            f"<{priority}>1 {timestamp_str} {self.hostname} "
            f"{self.app_name} {pid} {msgid} {structured_data} "
            f"{record.getMessage()}"
        )

    # ------------------------------------------------------------------
    # Override these two in subclasses for module-specific behaviour
    # ------------------------------------------------------------------

    def _get_message_id(self, record):
        """Generate a short message-id string for SNMP categorisation."""
        return 'WWAN_EVENT'

    def _build_structured_data(self, record):
        """Build the RFC 5424 structured-data field."""
        sd_elements = []

        wwan_data = []
        if hasattr(record, 'interface_number'):
            wwan_data.append(f'interface="{record.interface_number}"')
        if wwan_data:
            sd_elements.append(f'[wwan@32473 {" ".join(wwan_data)}]')

        origin_data = ['software="vyos-wwan"', 'version="1.0"']
        sd_elements.append(f'[origin@32473 {" ".join(origin_data)}]')

        return ''.join(sd_elements) if sd_elements else '-'


def setup_logging(logger_name: str,
                  app_name: str,
                  formatter_class=None,
                  level: int = logging.INFO):
    """Convenience helper used by every WWAN module.

    Returns a configured ``logging.Logger`` with a syslog handler
    (if ``/dev/log`` is available) and a console handler.
    """
    if formatter_class is None:
        formatter_class = RFC5424Formatter

    formatter = formatter_class(app_name)

    try:
        facility_num = RFC5424Formatter.FACILITY_MAP.get(app_name, 16)
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
