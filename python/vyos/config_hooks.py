#!/usr/bin/env python3
#
# Copyright (C) 2018 VyOS maintainers and contributors
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

import subprocess
import re
import argparse
import vyos.config
from vyos import ConfigError


# get list of VRRP groups with rfc3768-compatibility flag
def _vrrp_rfc3768_get():
	# define dict with VRRP groups
	vrrp_groups = {}

	# get configuration
	config = vyos.config.Config()

	config.set_level("")
	# roll through all VRRP groups
	for group_name in config.list_nodes("high-availability vrrp group"):
		config.set_level("high-availability vrrp group {0}".format(group_name))
		# check if this group have rfc3768-compatibility flag and not disabled
		if (not config.exists("disable") and config.exists("rfc3768-compatibility")):
			# create dict item with VRRP group data
			iface = config.return_value("interface")
			vrid = config.return_value("vrid")

			# create or append VRID to the item
			if iface not in vrrp_groups:
				vrrp_groups[iface] = { "vrid": [vrid] }
			else:
				vrrp_groups[iface]["vrid"].append(vrid)

	# return dict with interfaces as keys and VRRP configuration as value
	return vrrp_groups


# get iptables rule dict for chain in table
def _iptables_chain_get(proto, table, chain_name):
	# define dict with rules, iptables command and empty parser pattern
	rules = {}
	iptables_command, rule_pattern = None, None

	# tune variables for IP protocol
	if proto == "ipv4":
		iptables_command = "iptables -t {0} -L {1} -n -v -x --line-numbers".format(table, chain_name)
		rule_pattern = '^(?P<num>\d+) +(?P<pkts>\d+) +(?P<bytes>\d+) +(?P<target>[\w\-]+) +(?P<prot>\w+) +(?P<opt>[\w\-]+) +(?P<in>[\w\.\*\-]+) +(?P<out>[\w\.\*\-]+) +(?P<source>[\w\.\:\/]+) +(?P<destination>[\w\.\:\/]+) +(?P<details>.*)$'
	if proto == "ipv6":
		iptables_command = "ip6tables -t {0} -L {1} -n -v -x --line-numbers".format(table, chain_name)
		rule_pattern = '^(?P<num>\d+) +(?P<pkts>\d+) +(?P<bytes>\d+) +(?P<target>[\w\-]+) +(?P<prot>\w+) +(?P<in>[\w\.\*\-]+) +(?P<out>[\w\.\*\-]+) +(?P<source>[\w\.\:\/]+) +(?P<destination>[\w\.\:\/]+) +(?P<details>.*)$'

	# run iptables, save output and split it by lines
	iptables = subprocess.Popen(iptables_command, stdout=subprocess.PIPE, shell=True)
	iptables_out = iptables.stdout.read().decode().splitlines()

	# prepare regex for parsing rules
	rule = re.compile(rule_pattern)

	# parse each line and add information to dict
	for current_rule in iptables_out:
		current_rule_parsed = rule.search(current_rule)
		if current_rule_parsed:
			rules[current_rule_parsed.groupdict()["num"]] = current_rule_parsed.groupdict()

	# return dict with rule numbers as keys and information as values
	return rules


# get active firewall rules for interface
def _fw_iface_get(iface):
	# define list with rules
	iface_rules = []

	# get dicts with list of rules for IPv4 and IPv6 in all directions
	rules4_in = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_IN_HOOK")
	rules4_out = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_OUT_HOOK")
	rules4_local = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_LOCAL_HOOK")
	rules6_in = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_IN_HOOK")
	rules6_out = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_OUT_HOOK")
	rules6_local = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_LOCAL_HOOK")

	# add information to rules list
	for rule in rules4_in.values():
		current_iface = rule["in"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall name", "rule_type": "in", "target": rule["target"] }
			iface_rules.append(current_rule)
	for rule in rules4_out.values():
		current_iface = rule["out"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall name", "rule_type": "out", "target": rule["target"] }
			iface_rules.append(current_rule)
	for rule in rules4_local.values():
		current_iface = rule["in"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall name", "rule_type": "local", "target": rule["target"] }
			iface_rules.append(current_rule)
	for rule in rules6_in.values():
		current_iface = rule["in"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "in", "target": rule["target"] }
			iface_rules.append(current_rule)
	for rule in rules6_out.values():
		current_iface = rule["out"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "out", "target": rule["target"] }
			iface_rules.append(current_rule)
	for rule in rules6_local.values():
		current_iface = rule["in"]
		if iface == current_iface:
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "local", "target": rule["target"] }
			iface_rules.append(current_rule)

	# return list of firewall rules for interface
	return iface_rules


# get list of configured iptables rules for rfc3768-compatibility interfaces
def _fw_get_rfc3768():
	# define dict with rfc3768 rules
	rfc3768_rules = {}

	# get dicts with list of rules for IPv4 and IPv6 in all directions
	rules4_in = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_IN_HOOK")
	rules4_out = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_OUT_HOOK")
	rules4_local = _iptables_chain_get("ipv4", "filter", "VYATTA_FW_LOCAL_HOOK")
	rules6_in = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_IN_HOOK")
	rules6_out = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_OUT_HOOK")
	rules6_local = _iptables_chain_get("ipv6", "filter", "VYATTA_FW_LOCAL_HOOK")
	
	# check rules for VMAC interface
	vmac_regex = re.compile('^(?P<iface>[\w+\.]+\d+v\d+)$')
	for rule in rules4_in.values():
		current_iface = rule["in"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall name", "rule_type": "in", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]
	for rule in rules4_out.values():
		current_iface = rule["out"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall name", "rule_type": "out", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]
	for rule in rules4_local.values():
		current_iface = rule["in"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall name", "rule_type": "local", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]
	for rule in rules6_in.values():
		current_iface = rule["in"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "in", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]
	for rule in rules6_out.values():
		current_iface = rule["out"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "out", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]
	for rule in rules6_local.values():
		current_iface = rule["in"]
		if vmac_regex.fullmatch(current_iface):
			current_rule = { "rule_proto": "firewall ipv6-name", "rule_type": "local", "target": rule["target"] }
			rfc3768_rules[current_iface] = rfc3768_rules.get(current_iface, []) + [current_rule]

	# return dict with interfaces name as keys and rules information as values
	return rfc3768_rules


# configure firewall rules
def _firewall_set(operation, iface, direction, ruleset, iptype):
	subprocess.call("/opt/vyatta/sbin/vyatta-firewall.pl --update-interfaces {0} {1} {2} {3} \"{4}\"".format(operation, iface, direction, ruleset, iptype), shell=True)


# hooks for using during configuration process
class Hook:

	# sync firewall rules to VMAC interfaces
	def vrrp_firewall_sync():
		# get list VRRP groups with rfc3768-compatibility
		vrrp_groups = _vrrp_rfc3768_get()

		# get rules for parent interfaces for this groups and iptables rules for them
		parent_iface_rules = {}
		config_iface_vmac_rules = {}

		for iface, vrids in vrrp_groups.items():
			parent_iface_rules[iface] = _fw_iface_get(iface)
			for current_id in vrids["vrid"]:
				config_iface_vmac_rules[iface+"v"+current_id] = parent_iface_rules[iface]
		
		# add firewall rules for VMAC interfaces
		for iface, rules in config_iface_vmac_rules.items():
			for rule in rules:
				_firewall_set("update", iface, rule["rule_type"], rule["target"], rule["rule_proto"])

		# get list of current rules applied to VMAC interfaces
		active_iface_vmac_rules = _fw_get_rfc3768()

		# check if active rules configured properly and delete wrong/old items
		for iface, rules in active_iface_vmac_rules.items():
			for rule in rules:
				if rule not in config_iface_vmac_rules.get(iface, []):
					_firewall_set("delete", iface, rule["rule_type"], rule["target"], rule["rule_proto"])					


# standalone mode
if (__name__ == '__main__'):
	# define arguments
	parser = argparse.ArgumentParser()
	parser.add_argument("-hook", help="hook name", type=str, required=True)
	parser.add_argument("-hookargs", help="arguments for hook", type=str)
	command_arguments = parser.parse_args()

	# check an argument and run requested hook
	if command_arguments.hook == "vrrp_firewall_sync":
		Hook.vrrp_firewall_sync()
		exit(0)
	else:
		print("Error: there is no hook with name \"{0}\"".format(command_arguments.hook))
		exit(1)
