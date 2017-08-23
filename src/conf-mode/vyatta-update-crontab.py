#!/usr/bin/env python3
#
# vyatta-update-ctontab.pl: crontab generator
#
# Maintainer: Daniil Baturin <daniil@baturin.org>
#
# Copyright (C) 2013 SO3Group
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import io
import os
import re
import sys
sys.path.append("/usr/lib/python3/dist-packages/vyos/")
import config
from config import VyOSError


def update_crontab():
    conf = config.Config()
    count = 0


    default_user = "root"
    crontab = "/etc/cron.d/vyatta-crontab"
    crontab_header = "### Added by /opt/vyatta/sbin/vyatta-update-crontab.py ###\n"
    if not conf.exists("system task-scheduler task"):
        os.remove(crontab)
        return 0
    crontab_append = crontab_header

    conf.set_level("system task-scheduler task")
    tasks = conf.list_nodes("")

    for task in tasks:
        task = task.decode("utf-8")
        minutes = "*"
        hours = "*"
        days = "*"

        # Unused now
        months = "*"
        days_of_week = "*"
        try:
            user = conf.return_value(" ".join([task, "user"]))
        except VyOSError:
            user = default_user

        try:
           executable = conf.return_value(" ".join([task, "executable path"]))
           executable = executable.decode("utf-8")
        except VyOSError:
            raise VyOSError (task + "must define executable")

        try:
            arguments = conf.return_value(" ".join([task, "executable arguments"]))
        except VyOSError:
            arguments = ""

        try:
            interval = conf.return_value(" ".join([task, "interval"]))
        except VyOSError:
            interval = None

        try:
            crontab_spec = conf.return_value(" ".join([task, "crontab-spec"]))
        except:
            crontab_spec = None

        if interval and crontab_spec:
            raise VyOSError(task, "can not use interval and crontab-spec at the same time!")

        if interval:
            result = re.search(b"(\d+)([mdh]?)", interval)
            value = int(result.group(1))
            suffix = result.group(2)


            if not suffix or suffix == b"m":
                if value > 60:
                    raise VyOSError("Interval in minutes must not exceed 60!")
                minutes = "*/" + str(value)

            elif suffix == b"h":
                if value > 24:
                    raise VyOSError("Interval in hours must not exceed 24!")
                minutes = "0"
                hours = "*/" + str(value)

            elif suffix == b"d":
                if value > 31:
                    raise VyOSError("Interval in days must not exceed 31!")

                minutes = "0"
                hours = "0"
                days = "*/" + str(value)
            crontab_string = "{minutes} {hours} {days} {months} {days_of_week} {user} {executable} {arguments}\n".format(
                minutes=minutes,
                hours=hours,
                days=days,
                months=months,
                days_of_week=days_of_week,
                user=user,
                executable=executable,
                arguments=arguments
            )
        elif crontab_spec:
            crontab_string = "{crontab_spec) {user} {executable} {arguments}\n".format(
                crontab_spec=crontab_spec,
                user=user,
                executable=executable,
                arguments=arguments
            )
        else:
            raise VyOSError(task, "must define either interval or crontab-spec")
        crontab_append = crontab_append + crontab_string
        count = count + 1

    if count > 0:
        try:
            f = io.open(crontab, "w")
            f.write(crontab_append)
            f.close()
        except IOError:
            print("Could not open /etc/crontab for write")
    else:
        os.remove(crontab)

if __name__ == '__main__':
    try:
        update_crontab()

    except VyOSError:
        sys.exit(0)