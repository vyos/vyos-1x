#!/usr/bin/python3

import sys
import re

from signal import signal, SIGPIPE, SIG_DFL
from vyos.configtree import ConfigTree

signal(SIGPIPE,SIG_DFL)


config_string = sys.stdin.read().strip()

if not config_string:
    sys.exit(0)

# When used in conf mode pipe, the config given to the script is likely incomplete
# and breaks the "all top level nodes are neither tag nor leaf"
# invariant, so we wrap it into a fake node.
# Since nodes don't normally start with an underscore,
# __root__ is hygienic enough.
config_string = "__root__ {{ {0} \n }}".format(config_string)

config_re = re.compile("(set|comment)\s+__root__\s+(.*)")

config = ConfigTree(config_string)
commands = config.to_commands()
commands = config_re.sub("\\1 \\2", commands)

print(commands)
