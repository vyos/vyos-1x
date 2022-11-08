#!/usr/bin/env python3
#
# Copyright (C) 2017 VyOS maintainers and contributors
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 or later as
# published by the Feee Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#

import sys

from vyos.config import Config
from vyos import ConfigError
from vyos.task_scheduler import task_scheduler_apply
from vyos.task_scheduler import task_scheduler_generate
from vyos.task_scheduler import task_scheduler_verify 

from vyos import airbag
airbag.enable()

crontab_file = "/etc/cron.d/vyos-crontab"


def get_config(config=None):
    if config:
        conf = config
    else:
        conf = Config()
    conf.set_level("system task-scheduler task")
    task_names = conf.list_nodes("")
    tasks = []

    for name in task_names:
        interval = conf.return_value("{0} interval".format(name))
        spec = conf.return_value("{0} crontab-spec".format(name))
        executable = conf.return_value("{0} executable path".format(name))
        args = conf.return_value("{0} executable arguments".format(name))
        task = {
                "name": name,
                "interval": interval,
                "spec": spec,
                "executable": executable,
                "args": args
              }
        tasks.append(task)

    return tasks

def verify(tasks):
    task_scheduler_verify(tasks)

def generate(tasks):
     task_scheduler_generate(tasks, crontab_file)

def apply(config):
     task_scheduler_apply(config)

if __name__ == '__main__':
    try:
        c = get_config()
        verify(c)
        generate(c)
        apply(c)
    except ConfigError as e:
        print(e)
        sys.exit(1)
