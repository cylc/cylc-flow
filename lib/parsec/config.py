#!/usr/bin/env python2

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2018 NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.

import re
from parsec import ParsecError
from parsec.fileparse import parse
from parsec.util import printcfg
from parsec.validate import validate, check_compulsory, expand, validator
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import replicate, itemstr


class ItemNotFoundError(ParsecError):
    def __init__(self, msg):
        self.msg = 'ERROR: item not found: %s' % msg


class NotSingleItemError(ParsecError):
    def __init__(self, msg):
        self.msg = 'ERROR: not a singular item: %s' % msg


class config(object):
    "Object wrapper for parsec functions"

    def __init__(self, spec, upgrader=None, output_fname=None, tvars=None):

        self.sparse = OrderedDictWithDefaults()
        self.dense = OrderedDictWithDefaults()
        self.upgrader = upgrader
        self.tvars = tvars
        self.output_fname = output_fname
        self.checkspec(spec)
        self.spec = spec

    def checkspec(self, spec, parents=None):
        "check that the file spec is a nested dict of validators"
        if not parents:
            parents = []
        for key, value in spec.items():
            pars = parents + [key]
            if isinstance(value, dict):
                self.checkspec(value, pars)
            else:
                if not isinstance(value, validator):
                    raise ParsecError(
                        "Illegal file spec item: %s" % itemstr(
                            pars, repr(value)))

    def loadcfg(self, rcfile, title=""):
        """Parse a config file, upgrade or deprecate items if necessary,
        validate it against the spec, and if this is not the first load,
        combine/override with the existing loaded config."""

        sparse = parse(rcfile, self.output_fname, self.tvars)

        if self.upgrader is not None:
            self.upgrader(sparse, title)

        self.validate(sparse)

        if not self.sparse:
            self.sparse = sparse
        else:
            # Already loaded, override with new items.
            replicate(self.sparse, sparse)

    def validate(self, sparse):
        "Validate sparse config against the file spec."
        validate(sparse, self.spec)
        check_compulsory(sparse, self.spec)

    def expand(self):
        "Flesh out undefined items with defaults, if any, from the spec."
        if not self.dense:
            self.dense = expand(self.sparse, self.spec)

    def get(self, keys=None, sparse=False):
        """
        Retrieve items or sections, sparse or dense, by list of keys:
        [sec1,sec2,item] =>
            [sec1]
                [[sec2]]
                    item = value
        """
        if sparse:
            cfg = self.sparse
        else:
            self.expand()
            cfg = self.dense

        parents = []
        if keys:
            for key in keys:
                try:
                    cfg = cfg[key]
                except KeyError:
                    raise ItemNotFoundError(itemstr(parents, key))
                else:
                    parents.append(key)

        return cfg

    def idump(self, items=None, sparse=False, pnative=False, prefix='',
              oneline=False, none_str=''):
        """
        items is a list of --item style inputs:
           '[runtime][foo]script'.
        """
        mkeys = []
        null = True
        if items:
            for i in items:
                null = False
                i = i.lstrip('[')
                i = i.rstrip(']')
                j = re.split(r'\]\[*', i)
                mkeys.append(j)
        if null:
            mkeys = [[]]
        self.mdump(mkeys, sparse, pnative, prefix, oneline, none_str)

    def mdump(self, mkeys=None, sparse=False, pnative=False, prefix='',
              oneline=False, none_str=''):
        if oneline:
            items = []
            if mkeys:
                for keys in mkeys:
                    item = self.get(keys, sparse)
                    if isinstance(item, list) or isinstance(item, dict):
                        raise NotSingleItemError(itemstr(keys))
                    if not item:
                        item = none_str or "None"
                    items.append(str(item))
            # TODO - quote items if they contain spaces or comment delimiters?
            print prefix + ' '.join(items)
        elif mkeys:
            for keys in mkeys:
                self.dump(keys, sparse, pnative, prefix, none_str)

    def dump(self, keys=None, sparse=False, pnative=False, prefix='',
             none_str=''):
        if not keys:
            keys = []
        cfg = self.get(keys, sparse)
        if pnative:
            print cfg
        else:
            printcfg(cfg, prefix=prefix, level=len(keys), none_str=none_str)
