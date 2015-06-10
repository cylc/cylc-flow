#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2015 NIWA
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

"""Ordered Dictionary data structure used extensively in cylc."""

try:
    # first try the fast ordereddict C implementation.
    # DOWNLOAD: http://anthon.home.xs4all.nl/Python/ordereddict/
    # According to the ordereddict home page, this is much faster than
    # collections.OrderedDict.
    from _ordereddict import ordereddict as OrderedDict
except ImportError:
    try:
        # then try Python 2.7+ native module
        from collections import OrderedDict
    except ImportError:
        # then try the pre-2.7 backport from ActiveState
        # (packaged with cylc)
        from OrderedDictCompat import OrderedDict


class OrderedDictWithDefaults(OrderedDict):

    """Subclass to provide defaults fetching capability.

    Note that defining a '__missing__' method would work for foo[key],
    but doesn't for foo.get(key).

    """

    def __contains_no_default__(self, key):
        """No-default contains."""
        return key in list(self)

    def __contains_default__(self, key):
        """Make sure "key in foo" works with our defaults."""
        return key in self.keys()

    def __getitem__(self, key):
        """Override to look in our special .defaults attribute, if it exists."""
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            if hasattr(self, 'defaults'):
                return self.defaults[key]
            raise

    def __setitem__(self, *args, **kwargs):
        self.__contains__ = self.__contains_no_default__
        return_value = OrderedDict.__setitem__(self, *args, **kwargs)
        self.__contains__ = self.__contains_default__
        return return_value

    def keys(self):
        """Include the default keys, after the list of actually-set ones."""
        keys = list(self)
        for key in getattr(self, 'defaults', []):
            if key not in keys:
                keys.append(key)
        return keys

    def values(self):
        """Return a list of values, including default ones."""
        return [self[key] for key in self.keys()]

    def items(self):
        """Return key-value pairs, including default ones."""
        return [(key, self[key]) for key in self.keys()]

    def iterkeys(self):
        """Include default keys - no memory saving over .keys()."""
        for k in self.keys():
            yield k

    def itervalues(self):
        """Include default values - no memory saving over .values()."""
        for k in self.keys():
            yield self[k]

    def iteritems(self):
        """Include default key-value pairs - no memory saving over .items()"""
        for k in self.keys():
            yield (k, self[k])

    def __nonzero__(self):
        """Include any default keys in the nonzero calculation."""
        return bool(self.keys())

    def __repr__(self):
        non_default_items = []
        non_default_keys = list(self)
        for key in non_default_keys:
            non_default_items.append(key)
        default_items = []
        for key in getattr(self, 'defaults', []):
            if key not in non_default_keys:
                default_items.append(key)
        return "<" + type(self).__name__ + "({'': " + repr(non_default_items) + ", 'defaults':" + repr(default_items) + "})" + ")>\n"

    __contains__ = __contains_default__

