# Copyright (C) 2020 VyOS maintainers and contributors
#
# This library is free software; you can redistribute it and/or modify it under the terms of
# the GNU Lesser General Public License as published by the Free Software Foundation;
# either version 2.1 of the License, or (at your option) any later version.
#
# This library is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY;
# without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.
# See the GNU Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public License along with this library;
# if not, write to the Free Software Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA 02111-1307 USA 

# all named used as key (keywords) in this module are defined here.
# using variable name will allow the linter to warn on typos
# it separates our dict syntax from the xmldict one, making it easy to change

# we are redefining a python keyword "list" for ease


def found(word):
    """
    is the word following the format for a keyword
    """
    return word and word[0] == '[' and word[-1] == ']'


# root

version = '(version)'
tree = '(tree)'
priorities = '(priorities)'
owners = '(owners)'
tags = '(tags)'
default = '(default)'

# nodes

node = '[node]'

plainNode = '[plainNode]'
leafNode = '[leafNode]'
tagNode = '[tagNode]'

owner = '[owner]'

valueless = '[valueless]'
multi = '[multi]'
hidden = '[hidden]'

# properties

priority = '[priority]'

completion = '[completion]'
list = '[list]'
script = '[script]'
path = '[path]'

# help

help = '[help]'

summary = '[summary]'

valuehelp = '[valuehelp]'
format = 'format'
description = 'description'

# constraint

constraint = '[constraint]'
name = '[name]'

regex = '[regex]'
validator = '[validator]'
argument = '[argument]'

error = '[error]'

# created

node = '[node]'
