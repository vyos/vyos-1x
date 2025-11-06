#
# Copyright (C) VyOS Inc.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

from vyos.vpp import VPPControl


class SFlow:
    def __init__(self):
        self.vpp = VPPControl()

    def enable_sflow(self, interface):
        """Enable sFlow on interface"""
        self.vpp.api.sflow_enable_disable(
            enable_disable=True,
            hw_if_index=self.vpp.get_sw_if_index(interface),
        )

    def disable_sflow(self, interface):
        """Disable sFlow on interface"""
        self.vpp.api.sflow_enable_disable(
            enable_disable=False,
            hw_if_index=self.vpp.get_sw_if_index(interface),
        )

    def set_sampling_rate(self, sample_rate):
        """Set sFlow sampling-rate"""
        self.vpp.api.sflow_sampling_rate_set(sampling_N=sample_rate)

    def set_polling_interval(self, interval):
        """Set sFlow polling interval"""
        self.vpp.api.sflow_polling_interval_set(polling_S=interval)

    def set_header_bytes(self, header_bytes):
        """Set sFlow maximum header length in bytes"""
        self.vpp.api.sflow_header_bytes_set(header_B=header_bytes)
