#!/bin/sh
#
# Copyright (C) 2024 VyOS maintainers and contributors
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

declare -a vals
eval "vals=($(/sbin/sysctl -N -a|grep -E '^(fs.mqueue|net)\.|^(kernel.msgmax|kernel.msgmnb|kernel.msgmni|kernel.sem|kernel.shmall|kernel.shmmax|kernel.shmmni|kernel.shm_rmid_forced)$'))"
echo ${vals[@]}
exit 0
