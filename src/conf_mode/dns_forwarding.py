#!/usr/bin/env python3
#
# Copyright (C) 2018-2022 VyOS maintainers and contributors
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

import os

from netifaces import interfaces
from sys import exit
from glob import glob

from vyos.config import Config
from vyos.configdict import dict_merge
from vyos.hostsd_client import Client as hostsd_client
from vyos.template import render
from vyos.template import is_ipv6
from vyos.util import call
from vyos.util import chown
from vyos.util import dict_search
from vyos.xml import defaults

from vyos import ConfigError
from vyos import airbag
airbag.enable()

pdns_rec_user = pdns_rec_group = 'pdns'
pdns_rec_run_dir = '/run/powerdns'
pdns_rec_lua_conf_file = f'{pdns_rec_run_dir}/recursor.conf.lua'
pdns_rec_hostsd_lua_conf_file = f'{pdns_rec_run_dir}/recursor.vyos-hostsd.conf.lua'
pdns_rec_hostsd_zones_file = f'{pdns_rec_run_dir}/recursor.forward-zones.conf'
pdns_rec_config_file = f'{pdns_rec_run_dir}/recursor.conf'

hostsd_tag = 'static'

def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    base = ['service', 'dns', 'forwarding']
    if not conf.exists(base):
        return None

    dns = conf.get_config_dict(base, key_mangling=('-', '_'), get_first_key=True, no_tag_node_value_mangle=True)
    # We have gathered the dict representation of the CLI, but there are default
    # options which we need to update into the dictionary retrieved.
    default_values = defaults(base)
    # T2665 due to how defaults under tag nodes work, we must clear these out before we merge
    del default_values['authoritative_domain']
    dns = dict_merge(default_values, dns)

    # some additions to the default dictionary
    if 'system' in dns:
        base_nameservers = ['system', 'name-server']
        if conf.exists(base_nameservers):
            dns.update({'system_name_server': conf.return_values(base_nameservers)})

    if 'authoritative_domain' in dns:
        dns['authoritative_zones'] = []
        dns['authoritative_zone_errors'] = []
        for node in dns['authoritative_domain']:
            zonedata = dns['authoritative_domain'][node]
            if ('disable' in zonedata) or (not 'records' in zonedata):
                continue
            zone = {
                'name': node,
                'file': "{}/zone.{}.conf".format(pdns_rec_run_dir, node),
                'records': [],
            }

            recorddata = zonedata['records']

            for rtype in [ 'a', 'aaaa', 'cname', 'mx', 'ptr', 'txt', 'spf', 'srv', 'naptr' ]:
                if rtype not in recorddata:
                    continue
                for subnode in recorddata[rtype]:
                    if 'disable' in recorddata[rtype][subnode]:
                        continue

                    rdata = recorddata[rtype][subnode]

                    if rtype in [ 'a', 'aaaa' ]:
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'address' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: at least one address is required'.format(subnode, node))
                            continue

                        if subnode == 'any':
                            subnode = '*'

                        for address in rdata['address']:
                            zone['records'].append({
                                'name': subnode,
                                'type': rtype.upper(),
                                'ttl': rdata['ttl'],
                                'value': address
                            })
                    elif rtype in ['cname', 'ptr']:
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'target' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: target is required'.format(subnode, node))
                            continue

                        zone['records'].append({
                            'name': subnode,
                            'type': rtype.upper(),
                            'ttl': rdata['ttl'],
                            'value': '{}.'.format(rdata['target'])
                        })
                    elif rtype == 'mx':
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        del rdefaults['server']
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'server' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: at least one server is required'.format(subnode, node))
                            continue

                        for servername in rdata['server']:
                            serverdata = rdata['server'][servername]
                            serverdefaults = defaults(base + ['authoritative-domain', 'records', rtype, 'server']) # T2665
                            serverdata = dict_merge(serverdefaults, serverdata)
                            zone['records'].append({
                                'name': subnode,
                                'type': rtype.upper(),
                                'ttl': rdata['ttl'],
                                'value': '{} {}.'.format(serverdata['priority'], servername)
                            })
                    elif rtype == 'txt':
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'value' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: at least one value is required'.format(subnode, node))
                            continue

                        for value in rdata['value']:
                            zone['records'].append({
                                'name': subnode,
                                'type': rtype.upper(),
                                'ttl': rdata['ttl'],
                                'value': "\"{}\"".format(value.replace("\"", "\\\""))
                            })
                    elif rtype == 'spf':
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'value' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: value is required'.format(subnode, node))
                            continue

                        zone['records'].append({
                            'name': subnode,
                            'type': rtype.upper(),
                            'ttl': rdata['ttl'],
                            'value': '"{}"'.format(rdata['value'].replace("\"", "\\\""))
                        })
                    elif rtype == 'srv':
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        del rdefaults['entry']
                        rdata = dict_merge(rdefaults, rdata)

                        if not 'entry' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: at least one entry is required'.format(subnode, node))
                            continue

                        for entryno in rdata['entry']:
                            entrydata = rdata['entry'][entryno]
                            entrydefaults = defaults(base + ['authoritative-domain', 'records', rtype, 'entry']) # T2665
                            entrydata = dict_merge(entrydefaults, entrydata)

                            if not 'hostname' in entrydata:
                                dns['authoritative_zone_errors'].append('{}.{}: hostname is required for entry {}'.format(subnode, node, entryno))
                                continue

                            if not 'port' in entrydata:
                                dns['authoritative_zone_errors'].append('{}.{}: port is required for entry {}'.format(subnode, node, entryno))
                                continue

                            zone['records'].append({
                                'name': subnode,
                                'type': rtype.upper(),
                                'ttl': rdata['ttl'],
                                'value': '{} {} {} {}.'.format(entrydata['priority'], entrydata['weight'], entrydata['port'], entrydata['hostname'])
                            })
                    elif rtype == 'naptr':
                        rdefaults = defaults(base + ['authoritative-domain', 'records', rtype]) # T2665
                        del rdefaults['rule']
                        rdata = dict_merge(rdefaults, rdata)


                        if not 'rule' in rdata:
                            dns['authoritative_zone_errors'].append('{}.{}: at least one rule is required'.format(subnode, node))
                            continue

                        for ruleno in rdata['rule']:
                            ruledata = rdata['rule'][ruleno]
                            ruledefaults = defaults(base + ['authoritative-domain', 'records', rtype, 'rule']) # T2665
                            ruledata = dict_merge(ruledefaults, ruledata)
                            flags = ""
                            if 'lookup-srv' in ruledata:
                                flags += "S"
                            if 'lookup-a' in ruledata:
                                flags += "A"
                            if 'resolve-uri' in ruledata:
                                flags += "U"
                            if 'protocol-specific' in ruledata:
                                flags += "P"

                            if 'order' in ruledata:
                                order = ruledata['order']
                            else:
                                order = ruleno

                            if 'regexp' in ruledata:
                                regexp= ruledata['regexp'].replace("\"", "\\\"")
                            else:
                                regexp = ''

                            if ruledata['replacement']:
                                replacement = '{}.'.format(ruledata['replacement'])
                            else:
                                replacement = ''

                            zone['records'].append({
                                'name': subnode,
                                'type': rtype.upper(),
                                'ttl': rdata['ttl'],
                                'value': '{} {} "{}" "{}" "{}" {}'.format(order, ruledata['preference'], flags, ruledata['service'], regexp, replacement)
                            })

            dns['authoritative_zones'].append(zone)

    return dns

def verify(dns):
    # bail out early - looks like removal from running config
    if not dns:
        return None

    if 'listen_address' not in dns:
        raise ConfigError('DNS forwarding requires a listen-address')

    if 'allow_from' not in dns:
        raise ConfigError('DNS forwarding requires an allow-from network')

    # we can not use dict_search() when testing for domain servers
    # as a domain will contains dot's which is out dictionary delimiter.
    if 'domain' in dns:
        for domain in dns['domain']:
            if 'server' not in dns['domain'][domain]:
                raise ConfigError(f'No server configured for domain {domain}!')

    if 'dns64_prefix' in dns:
        dns_prefix = dns['dns64_prefix'].split('/')[1]
        # RFC 6147 requires prefix /96
        if int(dns_prefix) != 96:
            raise ConfigError('DNS 6to4 prefix must be of length /96')

    if ('authoritative_zone_errors' in dns) and dns['authoritative_zone_errors']:
        for error in dns['authoritative_zone_errors']:
            print(error)
        raise ConfigError('Invalid authoritative records have been defined')

    if 'system' in dns:
        if not 'system_name_server' in dns:
            print('Warning: No "system name-server" configured')

    return None

def generate(dns):
    # bail out early - looks like removal from running config
    if not dns:
        return None

    render(pdns_rec_config_file, 'dns-forwarding/recursor.conf.j2',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    render(pdns_rec_lua_conf_file, 'dns-forwarding/recursor.conf.lua.j2',
            dns, user=pdns_rec_user, group=pdns_rec_group)

    for zone_filename in glob(f'{pdns_rec_run_dir}/zone.*.conf'):
        os.unlink(zone_filename)

    if 'authoritative_zones' in dns:
        for zone in dns['authoritative_zones']:
            render(zone['file'], 'dns-forwarding/recursor.zone.conf.j2',
                    zone, user=pdns_rec_user, group=pdns_rec_group)


    # if vyos-hostsd didn't create its files yet, create them (empty)
    for file in [pdns_rec_hostsd_lua_conf_file, pdns_rec_hostsd_zones_file]:
        with open(file, 'a'):
            pass
        chown(file, user=pdns_rec_user, group=pdns_rec_group)

    return None

def apply(dns):
    if not dns:
        # DNS forwarding is removed in the commit
        call('systemctl stop pdns-recursor.service')

        if os.path.isfile(pdns_rec_config_file):
            os.unlink(pdns_rec_config_file)

        for zone_filename in glob(f'{pdns_rec_run_dir}/zone.*.conf'):
            os.unlink(zone_filename)
    else:
        ### first apply vyos-hostsd config
        hc = hostsd_client()

        # add static nameservers to hostsd so they can be joined with other
        # sources
        hc.delete_name_servers([hostsd_tag])
        if 'name_server' in dns:
            hc.add_name_servers({hostsd_tag: dns['name_server']})

        # delete all nameserver tags
        hc.delete_name_server_tags_recursor(hc.get_name_server_tags_recursor())

        ## add nameserver tags - the order determines the nameserver order!
        # our own tag (static)
        hc.add_name_server_tags_recursor([hostsd_tag])

        if 'system' in dns:
            hc.add_name_server_tags_recursor(['system'])
        else:
            hc.delete_name_server_tags_recursor(['system'])

        # add dhcp nameserver tags for configured interfaces
        if 'system_name_server' in dns:
            for interface in dns['system_name_server']:
                # system_name_server key contains both IP addresses and interface
                # names (DHCP) to use DNS servers. We need to check if the
                # value is an interface name - only if this is the case, add the
                # interface based DNS forwarder.
                if interface in interfaces():
                    hc.add_name_server_tags_recursor(['dhcp-' + interface,
                                                      'dhcpv6-' + interface ])

        # hostsd will generate the forward-zones file
        # the list and keys() are required as get returns a dict, not list
        hc.delete_forward_zones(list(hc.get_forward_zones().keys()))
        if 'domain' in dns:
            hc.add_forward_zones(dns['domain'])

        # hostsd generates NTAs for the authoritative zones
        # the list and keys() are required as get returns a dict, not list
        hc.delete_authoritative_zones(list(hc.get_authoritative_zones()))
        if 'authoritative_zones' in dns:
            hc.add_authoritative_zones(list(map(lambda zone: zone['name'], dns['authoritative_zones'])))

        # call hostsd to generate forward-zones and its lua-config-file
        hc.apply()

        ### finally (re)start pdns-recursor
        call('systemctl restart pdns-recursor.service')

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        exit(1)
