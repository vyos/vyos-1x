#!/usr/bin/env python3
#
# Copyright (C) VyOS Inc.
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
# Called via systemd ExecStartPost= after snmpd starts.
# Reads the live engineBoots value from /var/lib/snmp/snmpd.conf and
# writes it to /config/snmp/engineboots.count only if the value differs.
# Fixes T8538: ensures the persistent counter is always in sync with
# what snmpd actually used, so the next restart increments correctly.

import os
import logging
import contextlib

import vyos.opmode

from vyos.utils.file import read_file
from vyos.utils.file import write_file

SNMPD_CONF = '/var/lib/snmp/snmpd.conf'
PERSIST_FILE = '/config/snmp/engineboots.count'

# Configure logging
logger = logging.getLogger(__name__)
logger.addHandler(logging.StreamHandler())
logger.setLevel(logging.DEBUG)


def _read_snmpd_engine_boots() -> int | None:
    """Return the engineBoots value from snmpd's persistent conf, or None."""

    content = read_file(SNMPD_CONF, defaultonfailure='', sudo=True)
    for line in content.splitlines():
        if line.startswith('engineBoots'):
            parts = line.split()
            if len(parts) < 2:
                continue
            _, value, *_ = parts
            with contextlib.suppress(ValueError):
                return int(value)

    return None


def _read_persist_engine_boots() -> int | None:
    """Return the currently saved engineBoots counter, or None."""

    raw = read_file(PERSIST_FILE, defaultonfailure='')
    with contextlib.suppress(ValueError):
        return int(raw.strip())

    return None


if __name__ == '__main__':
    snmpd_boots = _read_snmpd_engine_boots()
    if snmpd_boots is None:
        raise vyos.opmode.DataUnavailable(
            f'Could not read engineBoots from {SNMPD_CONF}'
        )

    logger.debug(f'engineBoots from snmpd: {snmpd_boots}')

    persist_boots = _read_persist_engine_boots()
    logger.debug(f'engineBoots from persist file: {persist_boots}')

    if persist_boots == snmpd_boots:
        logger.debug('engineBoots already in sync, nothing to do')
    else:
        os.makedirs(os.path.dirname(PERSIST_FILE), exist_ok=True)
        write_file(PERSIST_FILE, str(snmpd_boots))
        logger.debug(f'engineBoots updated: {persist_boots} -> {snmpd_boots}')
