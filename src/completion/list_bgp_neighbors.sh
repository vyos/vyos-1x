#!/bin/bash
# Copyright VyOS maintainers and contributors <maintainers@vyos.io>
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

# Return BGP neighbor identifiers from CLI. Selectors:
#   --ipv4         IPv4 address peers
#   --ipv6         IPv6 address peers
#   --interfaces   peers that are neither IPv4 nor IPv6 addresses (interfaces)
#   --peer-groups  configured peer-group names
# Selectors are additive and may be combined freely. With --all-vrfs, neighbors
# from the default VRF and every configured VRF are merged and deduplicated.

ipv4=0
ipv6=0
interfaces=0
vrf_name=""
all_vrfs=0
peer_groups=0

while [[ "$#" -gt 0 ]]; do
    case $1 in
        -4|--ipv4) ipv4=1 ;;
        -6|--ipv6) ipv6=1 ;;
        -b|--both)
            # Deprecated: alias for --ipv4 --ipv6 --interfaces
            ipv4=1; ipv6=1; interfaces=1
            ;;
        --interfaces) interfaces=1 ;;
        --vrf) vrf_name=$2; shift ;;
        --all-vrfs) all_vrfs=1 ;;
        --peer-groups) peer_groups=1 ;;
        *) echo "Unknown parameter passed: $1" >&2 ;;
    esac
    shift
done

if [[ $all_vrfs -eq 1 && -n $vrf_name ]]; then
    echo "Error: --all-vrfs and --vrf are mutually exclusive" >&2
    exit 1
fi

# Wrap `cli-shell-api listActiveNodes` and append its (shell-quoted) output
# to the named array. The API is trusted to return safely quoted tokens,
# which is why `eval` is acceptable here -- it is the documented contract
# of cli-shell-api. Keeping the eval in one place makes the trust boundary
# explicit and easy to audit.
#
# Usage: _list_active_nodes <out_array_name> <path...>
_list_active_nodes() {
    local _out=$1; shift
    local _raw
    if ! _raw=$(cli-shell-api listActiveNodes "$@" 2>/dev/null); then
        return 0   # node missing or no config session -- treat as empty
    fi

    eval "${_out}+=(${_raw})"
}

declare -a vals=()
declare -a pg_vals=()

# Build the list of VRFs to traverse. The empty string represents the default
# VRF (no `vrf name <X>` prefix); any other value is the name of a configured
# VRF. This unifies the three cases (--all-vrfs, --vrf <name>, neither) into a
# single loop and avoids duplicating the collection logic.
declare -a _vrf_list=("")    # default VRF is always included

if (( all_vrfs )); then
    _list_active_nodes _vrf_list vrf name
elif [[ -n $vrf_name ]]; then
    _vrf_list=("$vrf_name")
fi

# Collect neighbors -- and optionally peer-groups -- from every VRF in the list.
for _vrf in "${_vrf_list[@]}"; do
    declare -a _path=()
    [[ -n $_vrf ]] && _path=(vrf name "$_vrf")
    _list_active_nodes vals "${_path[@]}" protocols bgp neighbor
    if (( peer_groups )); then
        _list_active_nodes pg_vals "${_path[@]}" protocols bgp peer-group
    fi
done

# Deduplicate when multiple VRFs may have contributed entries. A single source
# cannot produce duplicates, so the sort pipe is skipped in that case.
if (( ${#_vrf_list[@]} > 1 )); then
    if (( ${#vals[@]} > 1 )); then
        mapfile -t vals < <(printf '%s\n' "${vals[@]}" | LC_ALL=C sort -u)
    fi
    if (( ${#pg_vals[@]} > 1 )); then
        mapfile -t pg_vals < <(printf '%s\n' "${pg_vals[@]}" | LC_ALL=C sort -u)
    fi
fi

# Print neighbors from `vals` matching the requested selectors. The fast path
# below avoids any per-token filtering when all three neighbor categories
# (--ipv4, --ipv6, --interfaces) are requested -- in that case every entry in
# `vals` matches by definition.
_print_neighbors() {
    # Fast path: every neighbor is either v4, v6 or an interface, so when all
    # three are requested no classification is needed.
    if (( ipv4 && ipv6 && interfaces )); then
        (( ${#vals[@]} )) && printf '%s ' "${vals[@]}"
        return
    fi

    local peer
    for peer in "${vals[@]}"; do
        if ipaddrcheck --is-ipv4-single "$peer" >/dev/null 2>&1; then
            (( ipv4 )) && printf '%s ' "$peer"
        elif ipaddrcheck --is-ipv6-single "$peer" >/dev/null 2>&1; then
            (( ipv6 )) && printf '%s ' "$peer"
        else
            # Anything that is neither an IPv4 nor an IPv6 address is treated
            # as an interface name.
            (( interfaces )) && printf '%s ' "$peer"
        fi
    done
}

# Require at least one selector.
if (( ipv4 == 0 && ipv6 == 0 && interfaces == 0 && peer_groups == 0 )); then
    cat >&2 <<'EOF'
Usage:
  -4|--ipv4        list IPv4 address peers
  -6|--ipv6        list IPv6 address peers
  --interfaces     list interface peers (peers that are not IP addresses)
  --peer-groups    list configured peer-group names
  -b|--both        deprecated -- alias for --ipv4 --ipv6 --interfaces
  --vrf <name>     apply command to given VRF (optional)
  --all-vrfs       list neighbors across all VRFs (deduplicated)
EOF
    exit 1
fi

# Build the leading completion-help placeholders shown to the user.
declare -a _hdr=()
(( ipv4 )) && _hdr+=('<x.x.x.x>')
(( ipv6 )) && _hdr+=('<h:h:h:h:h:h:h:h>')
(( interfaces )) && _hdr+=('<interface>')
(( peer_groups )) && _hdr+=('<text>')

(( ${#_hdr[@]} )) && printf '%s ' "${_hdr[@]}"

if (( ipv4 || ipv6 || interfaces )); then
    _print_neighbors
fi

if (( peer_groups )) && (( ${#pg_vals[@]} )); then
    printf '%s ' "${pg_vals[@]}"
fi

exit 0
