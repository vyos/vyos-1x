# certbot_util -- adaptation of certbot_nginx name matching functions for VyOS
# https://github.com/certbot/certbot/blob/master/LICENSE.txt

from certbot_nginx._internal import parser

NAME_RANK = 0
START_WILDCARD_RANK = 1
END_WILDCARD_RANK = 2
REGEX_RANK = 3

def _rank_matches_by_name(server_block_list, target_name):
    """Returns a ranked list of server_blocks that match target_name.
    Adapted from the function of the same name in
    certbot_nginx.NginxConfigurator
    """
    matches = []
    for server_block in server_block_list:
        name_type, name = parser.get_best_match(target_name,
                                                server_block['name'])
        if name_type == 'exact':
            matches.append({'vhost': server_block,
                            'name': name,
                            'rank': NAME_RANK})
        elif name_type == 'wildcard_start':
            matches.append({'vhost': server_block,
                            'name': name,
                            'rank': START_WILDCARD_RANK})
        elif name_type == 'wildcard_end':
            matches.append({'vhost': server_block,
                            'name': name,
                            'rank': END_WILDCARD_RANK})
        elif name_type == 'regex':
            matches.append({'vhost': server_block,
                            'name': name,
                            'rank': REGEX_RANK})

    return sorted(matches, key=lambda x: x['rank'])

def _select_best_name_match(matches):
    """Returns the best name match of a ranked list of server_blocks.
    Adapted from the function of the same name in
    certbot_nginx.NginxConfigurator
    """
    if not matches:
        return None
    elif matches[0]['rank'] in [START_WILDCARD_RANK, END_WILDCARD_RANK]:
        rank = matches[0]['rank']
        wildcards = [x for x in matches if x['rank'] == rank]
        return max(wildcards, key=lambda x: len(x['name']))['vhost']
    else:
        return matches[0]['vhost']

def choose_server_block(server_block_list, target_name):
    matches = _rank_matches_by_name(server_block_list, target_name)
    server_blocks = [x for x in [_select_best_name_match(matches)]
                     if x is not None]
    return server_blocks

