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

from vyos.xml import kw

# As we index by key, the name is first and then the data:
# {'dummy': {
#   '[node]': '[tagNode]',
#   'address': { ... }
# } }

# so when we encounter a tagNode, we are really encountering
# the tagNode data.


class XML(dict):
    def __init__(self):
        self[kw.tree] = {}
        self[kw.priorities] = {}
        self[kw.owners] = {}
        self[kw.default] = {}
        self[kw.tags] = []

        dict.__init__(self)

        self.tree = self[kw.tree]
        # the options which matched the last incomplete world we had
        # or the last word in a list
        self.options = []
        # store all the part of the command we processed
        self.inside = []
        # should we check the data pass with the constraints
        self.check = False
        # are we still typing a word
        self.filling = False
        # do what have the tagNode value ?
        self.filled = False
        # last word seen
        self.word = ''
        # do we have all the data we want ?
        self.final = False
        # do we have too much data ?
        self.extra = False
        # what kind of node are we in plain vs data not
        self.plain = True

    def reset(self):
        self.tree = self[kw.tree]
        self.options = []
        self.inside = []
        self.check = False
        self.filling = False
        self.filled = False
        self.word = ''
        self.final = False
        self.extra = False
        self.plain = True

    # from functools import lru_cache
    # @lru_cache(maxsize=100)
    # XXX: need to use cachetool instead - for later

    def traverse(self, cmd):
        self.reset()

        # using split() intead of split(' ') eats the final ' '
        words = cmd.split(' ')
        passed = []
        word = ''
        data_node = False
        space = False

        while words:
            word = words.pop(0)
            space = word == ''
            perfect = False
            if word in self.tree:
                passed = []
                perfect = True
                self.tree = self.tree[word]
                data_node = self.tree[kw.node]
                self.inside.append(word)
                word = ''
                continue
            if word and data_node:
                passed.append(word)

        is_valueless = self.tree.get(kw.valueless, False)
        is_leafNode = data_node == kw.leafNode
        is_dataNode = data_node in (kw.leafNode, kw.tagNode)
        named_options = [_ for _ in self.tree if not kw.found(_)]

        if is_leafNode:
            self.final = is_valueless or len(passed) > 0
            self.extra = is_valueless and len(passed) > 0
            self.check = len(passed) >= 1
        else:
            self.final = False
            self.extra = False
            self.check = len(passed) == 1 and not space

        if self.final:
            self.word = ' '.join(passed)
        else:
            self.word = word

        if self.final:
            self.filling = True
        else:
            self.filling = not perfect and bool(cmd and word != '')

        self.filled = self.final or (is_dataNode and len(passed) > 0 and word == '')

        if is_dataNode and len(passed) == 0:
            self.options = []
        elif word:
            if data_node != kw.plainNode or len(passed) == 1:
                self.options = [_ for _ in self.tree if _.startswith(word)]
            else:
                self.options = []
        else:
            self.options = named_options

        self.plain = not is_dataNode

        # self.debug()

        return self.word

    def speculate(self):
        if len(self.options) == 1:
            self.tree = self.tree[self.options[0]]
            self.word = ''
            if self.tree.get(kw.node,'') not in (kw.tagNode, kw.leafNode):
                self.options = [_ for _ in self.tree if not kw.found(_)]

    def checks(self, cmd):
        # as we move thought the named node twice
        # the first time we get the data with the node
        # and the second with the pass parameters
        xml = self[kw.tree]

        words = cmd.split(' ')
        send = True
        last = []
        while words:
            word = words.pop(0)
            if word in xml:
                xml = xml[word]
                send = True
                last = []
                continue
            if xml[kw.node] in (kw.tagNode, kw.leafNode):
                if kw.constraint in xml:
                    if send:
                        yield (word, xml[kw.constraint])
                        send = False
                    else:
                        last.append((word, None))
        if len(last) >= 2:
            yield last[0]

    def summary(self):
        yield ('enter', '[ summary ]', str(self.inside))

        if kw.help not in self.tree:
            yield ('skip', '[ summary ]', str(self.inside))
            return

        if self.filled:
            return

        yield('', '', '\nHelp:')

        if kw.help in self.tree:
            summary = self.tree[kw.help].get(kw.summary)
            values = self.tree[kw.help].get(kw.valuehelp, [])
            if summary:
                yield(summary, '', '')
            for value in values:
                yield(value[kw.format], value[kw.description], '')

    def constraint(self):
        yield ('enter', '[ constraint ]', str(self.inside))

        if kw.help in self.tree:
            yield ('skip', '[ constraint ]', str(self.inside))
            return
        if kw.error not in self.tree:
            yield ('skip', '[ constraint ]', str(self.inside))
            return
        if not self.word or self.filling:
            yield ('skip', '[ constraint ]', str(self.inside))
            return

        yield('', '', '\nData Constraint:')

        yield('', 'constraint', str(self.tree[kw.error]))

    def listing(self):
        yield ('enter', '[ listing ]', str(self.inside))

        # only show the details when we passed the tagNode data
        if not self.plain and not self.filled:
            yield ('skip', '[ listing ]', str(self.inside))
            return

        yield('', '', '\nPossible completions:')

        options = list(self.tree.keys())
        options.sort()
        for option in options:
            if kw.found(option):
                continue
            if not option.startswith(self.word):
                continue
            inner = self.tree[option]
            prefix = '+> ' if inner.get(kw.node, '') != kw.leafNode else '   '
            if kw.help in inner:
                yield (prefix + option, inner[kw.help].get(kw.summary), '')
            else:
                yield (prefix + option, '(no help available)', '')

    def debug(self):
        print('------')
        print("word    '%s'" % self.word)
        print("filling " + str(self.filling))
        print("filled  " + str(self.filled))
        print("final   " + str(self.final))
        print("extra   " + str(self.extra))
        print("plain   " + str(self.plain))
        print("options " + str(self.options))

    # from functools import lru_cache
    # @lru_cache(maxsize=100)
    # XXX: need to use cachetool instead - for later

    def defaults(self, lpath, flat):
        d = self[kw.default]
        for k in lpath:
            d = d[k]

        if not flat:
            r = {}
            for k in d:
                under = k.replace('-','_')
                if isinstance(d[k],dict):
                    r[under] = self.defaults(lpath + [k], flat)
                    continue
                r[under] = d[k]	
            return r

        def _flatten(inside, index, d):
            r = {}
            local = inside[index:]
            prefix = '_'.join(_.replace('-','_') for _ in local) + '_' if local else ''
            for k in d:
                under = prefix + k.replace('-','_')
                level = inside + [k]
                if isinstance(d[k],dict):
                    r.update(_flatten(level, index, d[k]))
                    continue
                if self.is_multi(level, with_tag=False):
                    r[under] = [_.strip() for _ in d[k].split(',')]
                    continue
                r[under] = d[k]
            return r

        return _flatten(lpath, len(lpath), d)

    # from functools import lru_cache
    # @lru_cache(maxsize=100)
    # XXX: need to use cachetool instead - for later

    def _tree(self, lpath, with_tag=True):
        """
        returns the part of the tree searched or None if it does not exists
        if with_tag is set, this is a configuration path (with tagNode names)
        and tag name will be removed from the path when traversing the tree
        """
        tree = self[kw.tree]
        spath = lpath.copy()
        while spath:
            p = spath.pop(0)
            if p not in tree:
                return None
            tree = tree[p]
            if with_tag and spath and tree[kw.node] == kw.tagNode:
                spath.pop(0)
        return tree

    def _get(self, lpath, tag, with_tag=True):
        return self._tree(lpath + [tag], with_tag)

    def is_multi(self, lpath, with_tag=True):
        return self._get(lpath, kw.multi, with_tag) is True

    def is_tag(self, lpath, with_tag=True):
        return self._get(lpath, kw.node, with_tag) == kw.tagNode

    def is_leaf(self, lpath, with_tag=True):
        return self._get(lpath, kw.node, with_tag) == kw.leafNode

    def exists(self, lpath, with_tag=True):
        return self._get(lpath, kw.node, with_tag) is not None
