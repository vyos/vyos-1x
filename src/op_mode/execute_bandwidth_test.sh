#!/bin/sh
#
# Copyright (C) 2020 VyOS maintainers and contributors
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

if ipaddrcheck --is-ipv6 $1; then
    # Set address family to IPv6 when an IPv6 address was specified
    OPT="-V"
elif [[ $(dig $1 AAAA +short | grep -v '\.$' | wc -l) -gt 0 ]]; then
    # CNAME is also part of the dig answer thus we must remove any
    # CNAME response and only shot the AAAA response(s), this is done
    # by grep -v '\.$'

    # Set address family to IPv6 when FQDN has at least one AAAA record
    OPT="-V"
else
    # It's not IPv6, no option needed
    OPT=""
fi

/usr/bin/iperf $OPT -c $1 $2

