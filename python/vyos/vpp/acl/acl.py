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


NO_ACL_INDEX = 0xFFFFFFFF


class Acl:
    def __init__(self):
        self.vpp = VPPControl()

    def get_acl_index_by_tag(self, tag):
        """Get ACL index by tag name
        https://github.com/FDio/vpp/blob/21c641f9356da5137760cdc799127064c8c1fd31/src/plugins/acl/acl.api
        """
        for acl in self.vpp.api.acl_dump(acl_index=NO_ACL_INDEX):
            if acl.tag == tag:
                return acl.acl_index
        return NO_ACL_INDEX

    def add_replace_acl(self, tag, rules):
        """Add new ACL or replace existing one"""
        self.vpp.api.acl_add_replace(
            tag=tag,
            acl_index=self.get_acl_index_by_tag(tag),
            count=len(rules),
            r=rules,
        )

    def delete_acl(self, tag):
        """Delete existing ACL"""
        self.vpp.api.acl_del(acl_index=self.get_acl_index_by_tag(tag))

    def add_acl_interface(self, interface, input_tags, output_tags):
        """Add or replace ACLs on interface"""
        acls = []
        for tag in input_tags:
            acl_index = self.get_acl_index_by_tag(tag)
            acls.append(acl_index)
        for tag in output_tags:
            acl_index = self.get_acl_index_by_tag(tag)
            acls.append(acl_index)
        self.vpp.api.acl_interface_set_acl_list(
            sw_if_index=self.vpp.get_sw_if_index(interface),
            count=len(acls),
            n_input=len(input_tags),
            acls=acls,
        )

    def delete_acl_interface(self, interface):
        """Delete ACLs from interface"""
        self.vpp.api.acl_interface_set_acl_list(
            sw_if_index=self.vpp.get_sw_if_index(interface),
            count=0,
        )

    def get_mac_acl_index_by_tag(self, tag):
        """Get mac ACL by tag name"""
        for acl in self.vpp.api.macip_acl_dump():
            if acl.tag == tag:
                return acl.acl_index
        return NO_ACL_INDEX

    def add_replace_acl_mac(self, tag, rules):
        """Add or replace existing mac ACL"""
        self.vpp.api.macip_acl_add_replace(
            tag=tag,
            acl_index=self.get_mac_acl_index_by_tag(tag),
            count=len(rules),
            r=rules,
        )

    def delete_acl_mac(self, tag):
        """Delete existing mac ACL"""
        self.vpp.api.macip_acl_del(acl_index=self.get_mac_acl_index_by_tag(tag))

    def add_acl_mac_interface(self, interface, tag):
        """Add or replace mac ACLs on interface"""
        self.vpp.api.macip_acl_interface_add_del(
            sw_if_index=self.vpp.get_sw_if_index(interface),
            acl_index=self.get_mac_acl_index_by_tag(tag),
            is_add=True,
        )

    def delete_acl_mac_interface(self, interface):
        """Delete mac ACLs from interface"""
        self.vpp.api.macip_acl_interface_add_del(
            sw_if_index=self.vpp.get_sw_if_index(interface),
            is_add=False,
        )
