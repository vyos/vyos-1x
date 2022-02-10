#!/usr/bin/env python3
#
# Copyright (C) 2022 VyOS maintainers and contributors
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

from re import split as re_split
from sys import exit

from hurry import filesize
from tabulate import tabulate
from vici import Session as vici_session

from vyos.util import seconds_to_human


def convert(text):
    return int(text) if text.isdigit() else text.lower()


def alphanum_key(key):
    return [convert(c) for c in re_split('([0-9]+)', str(key))]


def format_output(sas):
    sa_data = []

    for sa in sas:
        for parent_sa in sa.values():
            # create an item for each child-sa
            for child_sa in parent_sa.get('child-sas', {}).values():
                # prepare a list for output data
                sa_out_name = sa_out_state = sa_out_uptime = sa_out_bytes = sa_out_packets = sa_out_remote_addr = sa_out_remote_id = sa_out_proposal = 'N/A'

                # collect raw data
                sa_name = child_sa.get('name')
                sa_state = child_sa.get('state')
                sa_uptime = child_sa.get('install-time')
                sa_bytes_in = child_sa.get('bytes-in')
                sa_bytes_out = child_sa.get('bytes-out')
                sa_packets_in = child_sa.get('packets-in')
                sa_packets_out = child_sa.get('packets-out')
                sa_remote_addr = parent_sa.get('remote-host')
                sa_remote_id = parent_sa.get('remote-id')
                sa_proposal_encr_alg = child_sa.get('encr-alg')
                sa_proposal_integ_alg = child_sa.get('integ-alg')
                sa_proposal_encr_keysize = child_sa.get('encr-keysize')
                sa_proposal_dh_group = child_sa.get('dh-group')

                # format data to display
                if sa_name:
                    sa_out_name = sa_name.decode()
                if sa_state:
                    if sa_state == b'INSTALLED':
                        sa_out_state = 'up'
                    else:
                        sa_out_state = 'down'
                if sa_uptime:
                    sa_out_uptime = seconds_to_human(sa_uptime.decode())
                if sa_bytes_in and sa_bytes_out:
                    bytes_in = filesize.size(int(sa_bytes_in.decode()))
                    bytes_out = filesize.size(int(sa_bytes_out.decode()))
                    sa_out_bytes = f'{bytes_in}/{bytes_out}'
                if sa_packets_in and sa_packets_out:
                    packets_in = filesize.size(int(sa_packets_in.decode()),
                                               system=filesize.si)
                    packets_out = filesize.size(int(sa_packets_out.decode()),
                                                system=filesize.si)
                    sa_out_packets = f'{packets_in}/{packets_out}'
                if sa_remote_addr:
                    sa_out_remote_addr = sa_remote_addr.decode()
                if sa_remote_id:
                    sa_out_remote_id = sa_remote_id.decode()
                # format proposal
                if sa_proposal_encr_alg:
                    sa_out_proposal = sa_proposal_encr_alg.decode()
                if sa_proposal_encr_keysize:
                    sa_proposal_encr_keysize_str = sa_proposal_encr_keysize.decode()
                    sa_out_proposal = f'{sa_out_proposal}_{sa_proposal_encr_keysize_str}'
                if sa_proposal_integ_alg:
                    sa_proposal_integ_alg_str = sa_proposal_integ_alg.decode()
                    sa_out_proposal = f'{sa_out_proposal}/{sa_proposal_integ_alg_str}'
                if sa_proposal_dh_group:
                    sa_proposal_dh_group_str = sa_proposal_dh_group.decode()
                    sa_out_proposal = f'{sa_out_proposal}/{sa_proposal_dh_group_str}'

                # add a new item to output data
                sa_data.append([
                    sa_out_name, sa_out_state, sa_out_uptime, sa_out_bytes,
                    sa_out_packets, sa_out_remote_addr, sa_out_remote_id,
                    sa_out_proposal
                ])

    # return output data
    return sa_data


if __name__ == '__main__':
    try:
        session = vici_session()
        sas = list(session.list_sas())

        sa_data = format_output(sas)
        sa_data = sorted(sa_data, key=alphanum_key)

        headers = [
            "Connection", "State", "Uptime", "Bytes In/Out", "Packets In/Out",
            "Remote address", "Remote ID", "Proposal"
        ]
        output = tabulate(sa_data, headers)
        print(output)
    except PermissionError:
        print("You do not have a permission to connect to the IPsec daemon")
        exit(1)
    except ConnectionRefusedError:
        print("IPsec is not runing")
        exit(1)
    except Exception as e:
        print("An error occured: {0}".format(e))
        exit(1)
