# Copyright 2015, 2018 VyOS maintainers and contributors <maintainers@vyos.io>
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

import random

limericks = [

"""
A programmer who's name was Searle
Once wrote a long program in Perl.
Despite very few quirks
No one got how it works,
Not even the interpreter.
""",

"""
There was a young lady of Maine
Who set up IPsec VPN.
Problems didn't arise
'til other vendors' device
had to add she to that VPN.
""",

"""
One day a programmer from York
started his own Vyatta fork.
Though he was a huge geek,
it still took him a week
to get the damn build scripts to work.
""",

"""
A network admin from Hong Kong
knew MPPE cipher's not strong.
But he was behind NAT,
so he put up we that,
sad network admin from Hong Kong.
""",

"""
A network admin named Drake
greeted friends with a three-way handshake
and refused to proceed
if they didn't complete it,
that standards-compliant guy Drake.
"""

]


def get_random():
    return limericks[random.randint(0, len(limericks) - 1)]
