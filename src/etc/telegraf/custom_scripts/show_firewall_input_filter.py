#!/usr/bin/env python3

import json
import re
import time

from vyos.utils.process import cmd


def get_nft_filter_chains():
    """
    Get list of nft chains for table filter
    """
    try:
        nft = cmd('/usr/sbin/nft --json list table ip vyos_filter')
    except Exception:
        return []
    nft = json.loads(nft)
    chain_list = []

    for output in nft['nftables']:
        if 'chain' in output:
            chain = output['chain']['name']
            chain_list.append(chain)

    return chain_list


def get_nftables_details(name):
    """
    Get dict, counters packets and bytes for chain
    """
    command = f'/usr/sbin/nft list chain ip vyos_filter {name}'
    try:
        results = cmd(command)
    except:
        return {}

    # Trick to remove 'NAME_' from chain name in the comment
    # It was added to any chain T4218
    # counter packets 0 bytes 0 return comment "FOO default-action accept"
    comment_name = name.replace("NAME_", "")
    out = {}
    for line in results.split('\n'):
        comment_search = re.search(rf'{comment_name}[\- ](\d+|default-action)', line)
        if not comment_search:
            continue

        rule = {}
        rule_id = comment_search[1]
        counter_search = re.search(r'counter packets (\d+) bytes (\d+)', line)
        if counter_search:
            rule['packets'] = counter_search[1]
            rule['bytes'] = counter_search[2]

        rule['conditions'] = re.sub(r'(\b(counter packets \d+ bytes \d+|drop|reject|return|log)\b|comment "[\w\-]+")', '', line).strip()
        out[rule_id] = rule
    return out


def get_nft_telegraf(name):
    """
    Get data for telegraf in influxDB format
    """
    for rule, rule_config in get_nftables_details(name).items():
        print(f'nftables,table=vyos_filter,chain={name},'
              f'ruleid={rule} '
              f'pkts={rule_config["packets"]}i,'
              f'bytes={rule_config["bytes"]}i '
              f'{str(int(time.time()))}000000000')


chains = get_nft_filter_chains()

for chain in chains:
    get_nft_telegraf(chain)
