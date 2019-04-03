#!/usr/bin/env python3

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2019 NIWA & British Crown (Met Office) & Contributors.
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
from parsec.exceptions import (
    ParsecError, ItemNotFoundError, NotSingleItemError)
from parsec.fileparse import parse
from parsec.util import printcfg
from parsec.validate import parsec_validate
from parsec.OrderedDict import OrderedDictWithDefaults
from parsec.util import itemstr, m_override, replicate, un_many


class ParsecConfig(object):
    """Object wrapper for parsec functions."""

    def __init__(self, spec, upgrader=None, output_fname=None, tvars=None,
                 validator=None):
        self.sparse = OrderedDictWithDefaults()
        self.dense = OrderedDictWithDefaults()
        self.upgrader = upgrader
        self.tvars = tvars
        self.output_fname = output_fname
        self.spec = spec
        if validator is None:
            validator = parsec_validate
        self.validator = validator

    @staticmethod
    def checkspec(spec_root, parents=None):
        """Check that the file spec is a nested dict of specifications"""
        stack = [[spec_root, []]]
        while stack:
            spec, parents = stack.pop()
            for key, value in spec.items():
                pars = parents + [key]
                if isinstance(value, dict):
                    stack.append([value, pars])
                elif not isinstance(value, list):
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
        """Validate sparse config against the file spec."""
        return self.validator(sparse, self.spec)

    def expand(self):
        """Flesh out undefined items with defaults, if any, from the spec."""
        if not self.dense:
            dense = OrderedDictWithDefaults()
            # Populate dict with default values from the spec
            stack = [[dense, self.spec]]
            while stack:
                defs, spec = stack.pop()
                for key, val in spec.items():
                    if isinstance(val, dict):
                        if key not in defs:
                            defs[key] = OrderedDictWithDefaults()
                        stack.append((defs[key], spec[key]))
                    else:
                        try:
                            defs[key] = spec[key][1]
                        except IndexError:
                            if spec[key][0].endswith('_LIST'):
                                defs[key] = []
                            else:
                                defs[key] = None
            # override defaults with sparse values
            m_override(dense, self.sparse)
            un_many(dense)
            self.dense = dense

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
            print(prefix + ' '.join(items))
        elif mkeys:
            for keys in mkeys:
                self.dump(keys, sparse, pnative, prefix, none_str)

    def dump(self, keys=None, sparse=False, pnative=False, prefix='',
             none_str=''):
        if not keys:
            keys = []
        cfg = self.get(keys, sparse)
        if pnative:
            print(cfg)
        else:
            printcfg(cfg, prefix=prefix, level=len(keys), none_str=none_str)
