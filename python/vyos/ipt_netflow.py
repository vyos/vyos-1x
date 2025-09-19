# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of the GNU Lesser General Public
# License as published by the Free Software Foundation; either
# version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library.  If not, see <http://www.gnu.org/licenses/>.

# Package to stop/start ipt_NETFLOW kernel module

# Provides functions stop(), start() and set_watched_iptables_interfaces()

from vyos.utils.kernel import check_kmod
from vyos.utils.kernel import unload_kmod
from vyos.utils.process import cmd
from vyos import ConfigError

module_name = 'ipt_NETFLOW'
iptables_ingress_netflow_table = 'raw'
iptables_ingress_netflow_chain = 'PREROUTING'
iptables_egress_netflow_table = 'mangle'
iptables_egress_netflow_chain = 'POSTROUTING'


# get iptables rule dict for chain in table
def _iptables_get_rules(command, chain, table):
    # define list with rules
    rules = []

    # run iptables, save output and split it by lines
    iptables_command = f'{command} -vn -t {table} -L {chain}'
    tmp = cmd(iptables_command, message='Failed to get flows list')
    lines = tmp.splitlines()

    # Sample output to parse:
    #   vyos@vyos:~$ sudo iptables -vn -t raw -L PREROUTING
    #   Chain PREROUTING (policy ACCEPT 0 packets, 0 bytes)
    #   pkts bytes target     prot opt in     out     source               destination
    #      0     0 NETFLOW    0    --  eth0   *       0.0.0.0/0            0.0.0.0/0           NETFLOW

    # Check that format is as expected
    if len(lines) < 2:
        raise ConfigError(f'Unexpected output from {command}, too few lines')
    if not lines[0].startswith(f'Chain {chain}'):
        raise ConfigError(f'Unexpected first line in output of {command}: "{lines[0]}"')
    columns = lines[1].split()

    # parse each line and add information to list
    rulenum = 0
    for current_rule in lines[2:]:
        rulenum += 1
        current_rule_parsed = current_rule.split()
        current_rule_parsed = {
            columns[i]: current_rule_parsed[i]
            for i in range(min(len(current_rule_parsed), len(columns)))
        }
        if current_rule_parsed.get('target', '') != 'NETFLOW':
            continue

        rules.append(
            {
                'interface-in': current_rule_parsed.get("in", ''),
                'interface-out': current_rule_parsed.get("out", ''),
                'table': table,
                'rulenum': rulenum,
            }
        )

    # return list with rules
    return rules


def _iptables_config(command, configured_ifaces, direction):
    # define list of nftables commands to modify settings
    iptables_commands = []

    if direction == "ingress":
        iptables_table = iptables_ingress_netflow_table
        iptables_chain = iptables_ingress_netflow_chain
    elif direction == "egress":
        iptables_table = iptables_egress_netflow_table
        iptables_chain = iptables_egress_netflow_chain
    else:
        raise ConfigError(f'_iptables_config: Unexpected direction="{direction}"')

    # prepare extended list with configured interfaces
    configured_ifaces_extended = []
    for iface in configured_ifaces:
        configured_ifaces_extended.append({'iface': iface})

    # get currently configured interfaces with iptables rules
    active_rules = _iptables_get_rules(command, iptables_chain, iptables_table)

    # compare current active list with configured one and delete excessive interfaces, add missed
    active_ifaces = []
    interface_key = 'interface-out' if direction == "egress" else "interface-in"
    rulenums_delete = []
    for rule in active_rules:
        interface = rule[interface_key]
        if interface not in configured_ifaces:
            rulenums_delete.append(rule['rulenum'])
        else:
            active_ifaces.append({'iface': interface})

    # It is important to delete rule with bigger rulenum first, so that other
    # rulenums are not changed
    rulenums_delete.sort(reverse=True)
    for rulenum in rulenums_delete:
        iptables_commands.append(
            f'{command} -t {iptables_table} -D {iptables_chain} {rulenum}'
        )

    # do not create new rules for already configured interfaces
    for iface in active_ifaces:
        if iface in configured_ifaces_extended:
            configured_ifaces_extended.remove(iface)

    # create missed rules
    for iface_extended in configured_ifaces_extended:
        iface = iface_extended['iface']
        iface_option = "o" if direction == "egress" else "i"
        # iptables -t raw -A PREROUTING -j NETFLOW -i eth0
        rule_definition = f'{command} -t {iptables_table} -A {iptables_chain} -j NETFLOW -{iface_option} {iface}'
        iptables_commands.append(rule_definition)

    # change iptables
    for command in iptables_commands:
        cmd(command, raising=ConfigError)


def _iptables_config_v4_and_v6(configured_ifaces, direction):
    for command in 'iptables', 'ip6tables':
        _iptables_config(command, configured_ifaces, direction)


def set_watched_iptables_interfaces(ingress_interfaces, egress_interfaces):
    """
    Update iptables and ip6tables rules so that ipt_NETFLOW watches
    exact list of interfaces in ingress_interfaces for ingress table/chain
    and egress_interfaces for egress table/chain
    """
    _iptables_config_v4_and_v6(ingress_interfaces, 'ingress')
    _iptables_config_v4_and_v6(egress_interfaces, 'egress')


def stop():
    """
    Stop ipt_NETFLOW: remove all iptables rules that use it
    and remove module
    """
    set_watched_iptables_interfaces([], [])

    unload_kmod(module_name)


def start(ingress_interfaces, egress_interfaces):
    """
    Start ipt_NETFLOW:

    * Load ipt_NETFLOW kernel module
    * Install iptables and ip6tables rules for
      ingress_interfaces and egress_interfaces
    """

    check_kmod(module_name)

    set_watched_iptables_interfaces(ingress_interfaces, egress_interfaces)
