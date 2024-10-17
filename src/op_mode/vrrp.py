#!/usr/bin/env python3
#
# Copyright (C) 2018-2024 VyOS maintainers and contributors
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
import json
import sys
import typing

from jinja2 import Template

import vyos.opmode
from vyos.ifconfig import VRRP
from vyos.ifconfig.vrrp import VRRPNoData


stat_template = Template("""
{% for rec in instances %}
VRRP Instance: {{rec.instance}}
  Advertisements:
    Received: {{rec.advert_rcvd}}
    Sent: {{rec.advert_sent}}
  Became master: {{rec.become_master}}
  Released master: {{rec.release_master}}
  Packet Errors:
    Length: {{rec.packet_len_err}}
    TTL: {{rec.ip_ttl_err}}
    Invalid Type: {{rec.invalid_type_rcvd}}
    Advertisement Interval: {{rec.advert_interval_err}}
    Address List: {{rec.addr_list_err}}
  Authentication Errors:
    Invalid Type: {{rec.invalid_authtype}}
    Type Mismatch: {{rec.authtype_mismatch}}
    Failure: {{rec.auth_failure}}
  Priority Zero:
    Received: {{rec.pri_zero_rcvd}}
    Sent: {{rec.pri_zero_sent}}
{% endfor %}
""")

detail_template = Template("""
{%- for rec in instances %}
 VRRP Instance: {{rec.iname}}
   VRRP Version: {{rec.version}}
   State: {{rec.state}}
   {% if rec.state == 'BACKUP' -%}
   Master priority: {{ rec.master_priority }}
   {% if rec.version == 3 -%}
   Master advert interval: {{ rec.master_adver_int }}
   {% endif -%}
   {% endif -%}
   Wantstate: {{rec.wantstate}}
   Last transition: {{rec.last_transition}}
   Interface: {{rec.ifp_ifname}}
   {% if rec.dont_track_primary > 0 -%}
   VRRP interface tracking disabled
   {% endif -%}
   {% if rec.skip_check_adv_addr > 0 -%}
   Skip checking advert IP addresses
   {% endif -%}
   {% if rec.strict_mode > 0 -%}
   Enforcing strict VRRP compliance
   {% endif -%}
   Gratuitous ARP delay: {{rec.garp_delay}}
   Gratuitous ARP repeat: {{rec.garp_rep}}
   Gratuitous ARP refresh: {{rec.garp_refresh}}
   Gratuitous ARP refresh repeat: {{rec.garp_refresh_rep}}
   Gratuitous ARP lower priority delay: {{rec.garp_lower_prio_delay}}
   Gratuitous ARP lower priority repeat: {{rec.garp_lower_prio_rep}}
   Send advert after receive lower priority advert: {{rec.lower_prio_no_advert}}
   Send advert after receive higher priority advert: {{rec.higher_prio_send_advert}}
   Virtual Router ID: {{rec.vrid}}
   Priority: {{rec.base_priority}}
   Effective priority: {{rec.effective_priority}}
   Advert interval: {{rec.adver_int}} sec
   Accept: {{rec.accept}}
   Preempt: {{rec.nopreempt}}
   {% if rec.preempt_delay -%}
   Preempt delay: {{rec.preempt_delay}}
   {% endif -%}
   Promote secondaries: {{rec.promote_secondaries}}
   Authentication type: {{rec.auth_type}}
   {% if rec.vips %}
   Virtual IP ({{ rec.vips | length }}):
       {% for ip in rec.vips -%}
         {{ip}}
       {% endfor -%}
   {% endif -%}
   {% if rec.evips %}
   Virtual IP Excluded:
       {% for ip in rec.evips -%}
         {{ip}}
       {% endfor -%}
   {% endif -%}
   {% if rec.vroutes %}
   Virtual Routes:
       {% for route in rec.vroutes -%}
         {{route}}
       {% endfor -%}
   {% endif -%}
   {% if rec.vrules %}
   Virtual Rules:
       {% for rule in rec.vrules -%}
         {{rule}}
       {% endfor -%}
   {% endif -%}
   {% if rec.track_ifp %}
   Tracked interfaces:
       {% for ifp in rec.track_ifp -%}
         {{ifp}}
       {% endfor -%}
   {% endif -%}
   {% if rec.track_script %}
   Tracked scripts:
       {% for script in rec.track_script -%}
         {{script}}
       {% endfor -%}
   {% endif %}
   Using smtp notification: {{rec.smtp_alert}}
   Notify deleted: {{rec.notify_deleted}}
{% endfor %}
""")

# https://github.com/acassen/keepalived/blob/59c39afe7410f927c9894a1bafb87e398c6f02be/keepalived/include/vrrp.h#L126
VRRP_AUTH_NONE = 0
VRRP_AUTH_PASS = 1
VRRP_AUTH_AH = 2

# https://github.com/acassen/keepalived/blob/59c39afe7410f927c9894a1bafb87e398c6f02be/keepalived/include/vrrp.h#L417
VRRP_STATE_INIT = 0
VRRP_STATE_BACK = 1
VRRP_STATE_MAST = 2
VRRP_STATE_FAULT = 3

VRRP_AUTH_TO_NAME = {
    VRRP_AUTH_NONE: 'NONE',
    VRRP_AUTH_PASS: 'SIMPLE_PASSWORD',
    VRRP_AUTH_AH: 'IPSEC_AH',
}

VRRP_STATE_TO_NAME = {
    VRRP_STATE_INIT: 'INIT',
    VRRP_STATE_BACK: 'BACKUP',
    VRRP_STATE_MAST: 'MASTER',
    VRRP_STATE_FAULT: 'FAULT',
}


def _get_raw_data(group_name: str = None) -> list:
    """
    Retrieve raw JSON data for all VRRP groups.

    Args:
        group_name (str, optional): If provided, filters the data to only
            include the specified vrrp group.

    Returns:
        list: A list of raw JSON data for VRRP groups, filtered by group_name
            if specified.
    """
    try:
        output = VRRP.collect('json')
    except VRRPNoData as e:
        raise vyos.opmode.DataUnavailable(f'{e}')

    data = json.loads(output)

    if not data:
        return []

    if group_name is not None:
        for rec in data:
            if rec['data'].get('iname') == group_name:
                return [rec]
        return []
    return data


def _get_formatted_statistics_output(data: list) -> str:
    """
    Prepare formatted statistics output from the given data.

    Args:
        data (list): A list of dictionaries containing vrrp grop information
            and statistics.

    Returns:
        str: Rendered statistics output based on the provided data.
    """
    instances = list()
    for instance in data:
        instances.append(
            {'instance': instance['data'].get('iname'), **instance['stats']}
        )

    return stat_template.render(instances=instances)


def _process_field(data: dict, field: str, true_value: str, false_value: str):
    """
    Updates the given field in the data dictionary with a specified value based
        on its truthiness.

    Args:
        data (dict): The dictionary containing the field to be processed.
        field (str): The key representing the field in the dictionary.
        true_value (str): The value to set if the field's value is truthy.
        false_value (str): The value to set if the field's value is falsy.

    Returns:
        None: The function modifies the dictionary in place.
    """
    data[field] = true_value if data.get(field) else false_value


def _get_formatted_detail_output(data: list) -> str:
    """
    Prepare formatted detail information output from the given data.

    Args:
        data (list): A list of dictionaries containing vrrp grop information
            and statistics.

    Returns:
        str: Rendered detail info output based on the provided data.
    """
    instances = list()
    for instance in data:
        instance['data']['state'] = VRRP_STATE_TO_NAME.get(
            instance['data'].get('state'), 'unknown'
        )
        instance['data']['wantstate'] = VRRP_STATE_TO_NAME.get(
            instance['data'].get('wantstate'), 'unknown'
        )
        instance['data']['auth_type'] = VRRP_AUTH_TO_NAME.get(
            instance['data'].get('auth_type'), 'unknown'
        )
        _process_field(instance['data'], 'lower_prio_no_advert', 'false', 'true')
        _process_field(instance['data'], 'higher_prio_send_advert', 'true', 'false')
        _process_field(instance['data'], 'accept', 'Enabled', 'Disabled')
        _process_field(instance['data'], 'notify_deleted', 'Deleted', 'Fault')
        _process_field(instance['data'], 'smtp_alert', 'yes', 'no')
        _process_field(instance['data'], 'nopreempt', 'Disabled', 'Enabled')
        _process_field(instance['data'], 'promote_secondaries', 'Enabled', 'Disabled')
        instance['data']['vips'] = instance['data'].get('vips', False)
        instance['data']['evips'] = instance['data'].get('evips', False)
        instance['data']['vroutes'] = instance['data'].get('vroutes', False)
        instance['data']['vrules'] = instance['data'].get('vrules', False)

        instances.append(instance['data'])

    return detail_template.render(instances=instances)


def show_detail(
    raw: bool, group_name: typing.Optional[str] = None
) -> typing.Union[list, str]:
    """
    Display detailed information about the VRRP group.

    Args:
        raw (bool): If True, return raw data instead of formatted output.
        group_name (str, optional): Filter the data by a specific group name,
            if provided.

    Returns:
        list or str: Raw data if `raw` is True, otherwise a formatted detail
            output.
    """
    data = _get_raw_data(group_name)

    if raw:
        return data

    return _get_formatted_detail_output(data)


def show_statistics(
    raw: bool, group_name: typing.Optional[str] = None
) -> typing.Union[list, str]:
    """
    Display VRRP group statistics.

    Args:
        raw (bool): If True, return raw data instead of formatted output.
        group_name (str, optional): Filter the data by a specific group name,
            if provided.

    Returns:
        list or str: Raw data if `raw` is True, otherwise a formatted statistic
            output.
    """
    data = _get_raw_data(group_name)

    if raw:
        return data

    return _get_formatted_statistics_output(data)


def show_summary(raw: bool) -> typing.Union[list, str]:
    """
    Display a summary of VRRP group.

    Args:
        raw (bool): If True, return raw data instead of formatted output.

    Returns:
        list or str: Raw data if `raw` is True, otherwise a formatted summary output.
    """
    data = _get_raw_data()

    if raw:
        return data

    return VRRP.format(data)


if __name__ == '__main__':
    try:
        res = vyos.opmode.run(sys.modules[__name__])
        if res:
            print(res)
    except (ValueError, vyos.opmode.Error) as e:
        print(e)
        sys.exit(1)
