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
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import csv
import sys
from itertools import chain

import vyos.opmode
from vyos.configquery import ConfigTreeQuery
from vyos.utils.process import cmd

def _get_raw_data(command: str) -> dict:
    # Returns returns chronyc output as a dictionary

    # Initialize dictionary keys to align with output of
    # chrony -c. From some commands, its -c switch outputs
    # more parameters, make sure to include them all below.
    # See to chronyc(1) for definition of key variables
    match command:
        case "chronyc -c activity":
            keys: list = [
            'sources_online',
            'sources_offline',
            'sources_doing_burst_return_online',
            'sources_doing_burst_return_offline',
            'sources_with_unknown_address'
            ]

        case "chronyc -c sources":
            keys: list = [
            'm',
            's',
            'name_ip_address',
            'stratum',
            'poll',
            'reach',
            'last_rx',
            'last_sample_adj_offset',
            'last_sample_mes_offset',
            'last_sample_est_error'
            ]

        case "chronyc -c sourcestats":
            keys: list = [
            'name_ip_address',
            'np',
            'nr',
            'span',
            'frequency',
            'freq_skew',
            'offset',
            'std_dev'
            ]

        case "chronyc -c tracking":
            keys: list = [
            'ref_id',
            'ref_id_name',
            'stratum',
            'ref_time',
            'system_time',
            'last_offset',
            'rms_offset',
            'frequency',
            'residual_freq',
            'skew',
            'root_delay',
            'root_dispersion',
            'update_interval',
            'leap_status'
            ]

        case _:
            raise ValueError(f"Raw mode: of {command} is not implemented")

    # Get -c option command line output, splitlines,
    # and save comma-separated values as a flat list
    output = cmd(command).splitlines()
    values = csv.reader(output)
    values = list(chain.from_iterable(values))

    # Divide values into chunks of size keys and transpose
    if len(values) > len(keys):
       values = _chunk_list(values,keys)
       values = zip(*values)

    return dict(zip(keys, values))

def _chunk_list(in_list, n):
    # Yields successive n-sized chunks from in_list
    for i in range(0, len(in_list), len(n)):
        yield in_list[i:i + len(n)]

def _is_configured():
    # Check if ntp is configured
    config = ConfigTreeQuery()
    if not config.exists("service ntp"):
        raise vyos.opmode.UnconfiguredSubsystem("NTP service is not enabled.")

def show_activity(raw: bool):
    _is_configured()
    command = f'chronyc'

    if raw:
       command += f" -c activity"
       return _get_raw_data(command)
    else:
       command += f" activity"
       return cmd(command)

def show_sources(raw: bool):
    _is_configured()
    command = f'chronyc'

    if raw:
       command += f" -c sources"
       return _get_raw_data(command)
    else:
       command += f" sources -v"
       return cmd(command)

def show_tracking(raw: bool):
    _is_configured()
    command = f'chronyc'

    if raw:
       command += f" -c tracking"
       return _get_raw_data(command)
    else:
       command += f" tracking"
       return cmd(command)

def show_sourcestats(raw: bool):
    _is_configured()
    command = f'chronyc'

    if raw:
       command += f" -c sourcestats"
       return _get_raw_data(command)
    else:
       command += f" sourcestats -v"
       return cmd(command)

if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
