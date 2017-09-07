#!/usr/bin/env python3
#
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

#!/usr/bin/env python3
import io
import re
import sys
sys.path.append("/usr/lib/python3/dist-packages/vyos/")

from config import VyOSError, Config


class CronTask(Config):
    def __init__(self, task):

        self.task = task
        self.minutes = "*"
        self.hours = "*"
        self.days = "*"
        self.user = "root"
        self.executable = None
        self.arguments = ""
        self.interval = None
        self.crontab_spec = None
        self._cli_shell_api = "/bin/cli-shell-api"

        # Unused now
        self.months = "*"
        self.days_of_week = "*"
        super(CronTask, self).set_level("system task-scheduler task")
        try:
            self.user = super(CronTask, self).return_value(" ".join([self.task, "user"]))
        except VyOSError:
            pass

        try:
            byte_executable = super(CronTask, self).return_value(" ".join([self.task, "executable path"]))
            self.executable = byte_executable.decode("utf-8")
        except VyOSError:
            raise VyOSError (task + "must define executable")

        try:
            byte_arguments = super(CronTask, self).return_value(" ".join([self.task, "executable arguments"]))
            self.executable = byte_arguments.decode("utf-8")
        except VyOSError:
            pass

        try:
            self.interval = super(CronTask, self).return_value(" ".join([self.task, "interval"]))
        except VyOSError:
            self.interval = None

        try:
            byte_crontab_spec = super(CronTask, self).return_value(" ".join([self.task, "crontab-spec"]))
            self.crontab_spec = byte_crontab_spec
        except:
            self.crontab_spec = None


def get_config():
    conf = Config()
    conf.set_level("system task-scheduler task")
    tasks = conf.list_nodes("")
    list_of_instanses=[]
    for task in tasks:
        list_of_instanses.append(CronTask(task.decode("utf-8")))
    return list_of_instanses


def verify(config):
    for task in config:
        if task.interval and task.crontab_spec:
            raise VyOSError(task, "can not use interval and crontab-spec at the same time!")

        if task.interval:
            result = re.search(b"(\d+)([mdh]?)", task.interval)
            value = int(result.group(1))
            suffix = result.group(2)


            if not suffix or suffix == b"m":
                if value > 60:
                    raise VyOSError("Interval in minutes must not exceed 60!")
                task.minutes = "*/" + str(value)

            elif suffix == b"h":
                if value > 24:
                    raise VyOSError("Interval in hours must not exceed 24!")
                task.minutes = "0"
                task.hours = "*/" + str(value)

            elif suffix == b"d":
                if value > 31:
                    raise VyOSError("Interval in days must not exceed 31!")

                task.minutes = "0"
                task.hours = "0"
                task.days = "*/" + str(value)
        elif task.interval and task.crontab_spec:
            raise VyOSError(task, "must define either interval or crontab-spec")
    return None


def generate(config):
    crontab = "/etc/cron.d/vyatta-crontab"
    crontab_header = "### Added by /opt/vyatta/sbin/vyatta-update-crontab.py ###\n"
    crontab_append = crontab_header
    count = 0
    for task in config:
        if task.interval:
            crontab_string = "{minutes} {hours} {days} {months} {days_of_week} {user} {executable} {arguments}\n".format(
                minutes=task.minutes,
                hours=task.hours,
                days=task.days,
                months=task.months,
                days_of_week=task.days_of_week,
                user=task.user,
                executable=task.executable,
                arguments=task.arguments
            )
        elif task.crontab_spec:
            crontab_string = "{crontab_spec) {user} {executable} {arguments}\n".format(
                crontab_spec=task.crontab_spec,
                user=task.user,
                executable=task.executable,
                arguments=task.arguments
            )
        crontab_append = crontab_append + crontab_string
        count = count + 1
    if count > 0:
        try:
            f = io.open(crontab, "w")
            f.write(crontab_append)
            f.close()
        except IOError:
                print("Could not open /etc/crontab for write")


def apply(config):
    pass


if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except VyOSError:
        sys.exit(0)

