# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
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

from copy import deepcopy
import re
from textwrap import dedent

from cylc.flow.context_node import ContextNode
from cylc.flow.parsec.exceptions import (
    ItemNotFoundError,
    NotSingleItemError
)
from cylc.flow.parsec.fileparse import parse
from cylc.flow.parsec.util import printcfg
from cylc.flow.parsec.validate import parsec_validate, ParsecValidator as VDR
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.util import itemstr, m_override, replicate, un_many


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
                for node in spec:
                    if not node.is_leaf():
                        if node.name not in defs:
                            defs[node.name] = OrderedDictWithDefaults()
                        stack.append((defs[node.name], node))
                    else:
                        if node.default is ConfigNode.UNSET:
                            if node.vdr and node.vdr.endswith('_LIST'):
                                defs[node.name] = []
                            else:
                                defs[node.name] = None
                        else:
                            defs[node.name] = node.default
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
                except (KeyError, TypeError):
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


class ConfigNode(ContextNode):
    """A Cylc configuration schema, section, or setting.

    Attributes:
        vdr (str):
            The config type (i.e. parsec validator).
        options (list):
            List of possible options.
            TODO: allow this to be a dict with help info
        default (object):
            The default value.
        desc (str):
            A description of the config.
            Note this gets dedented and stripped.
        display_name (str):
            This is the user-facing name of the config.
            Note the regular ``name`` might be ``__MANY__``.
        meta (ConfigNode):
            Another ConfigNode to use as a template for this one.

            This is useful if you want to create a specific instance of
            a generic configuration e.g. ``[elephant]`` from ``[<animal>]``.

            Leaf nodes inherited from the generic config wil have
            ``meta=True``.

    """

    ROOT_NAME_FMT = '{display_name}'
    NODE_NAME_FMT = '[{display_name}]'
    LEAF_NAME_FMT = '{display_name}'
    SEP = ''

    UNSET = '*value unset*'

    __slots__ = ContextNode.__slots__ + (
        'vdr', 'options', 'default', 'desc', 'display_name', 'meta'
    )

    def __init__(
            self,
            name,
            vdr=VDR.V_STRING,
            default=UNSET,
            options=None,
            desc=None,
            meta=None
    ):
        display_name = name
        if name.startswith('<'):
            # if we use <...> as the name, this is a user-definable config
            # * we set the name (for internal use) to __MANY__
            # * we leave the display_name (for external use) unchanged
            name = '__MANY__'

        ContextNode.__init__(self, name)

        if meta:
            # inherit items from the template configuration
            self._children = deepcopy(meta._children)
            for child in self._children.values():
                # record that these configurations have been inherited
                # (this is used to prevent documenting settings twice)
                child.meta = True

        self.display_name = display_name
        self.vdr = vdr
        self.default = default
        self.options = options
        self.desc = dedent(desc).strip() if desc else None
        self.meta = meta

    def __repr__(self):
        parents = list(self.parents())
        itr = list(reversed(list(parents))) + [self]
        if len(parents) == 1 and self.is_leaf():
            itr.insert(1, '|')
        return ''.join(map(str, itr))
