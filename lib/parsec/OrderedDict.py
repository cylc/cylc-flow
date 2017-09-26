#!/usr/bin/env python

# THIS FILE IS PART OF THE CYLC SUITE ENGINE.
# Copyright (C) 2008-2017 NIWA
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
    # Python 2.7+ native.
    from collections import OrderedDict
except ImportError:
    # Pre-2.7 backport from ActiveState, packaged with Parsec.
    from OrderedDictCompat import OrderedDict


class OrderedDictWithDefaults(OrderedDict):

    """Subclass to provide defaults fetching capability.

    Note that defining a '__missing__' method would work for foo[key],
    but doesn't for foo.get(key).

    """

    def __init__(self, *args, **kwargs):
        """Allow a defaults argument."""
        self._allow_contains_default = True
        super(OrderedDictWithDefaults, self).__init__(*args, **kwargs)

    def __getitem__(self, key):
        """Override to look in our special defaults attribute, if it exists."""
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            if hasattr(self, 'defaults_'):
                return self.defaults_[key]
            raise

    def __setitem__(self, *args, **kwargs):
        """Make sure that we don't set the default value!"""
        self._allow_contains_default = False
        return_value = OrderedDict.__setitem__(self, *args, **kwargs)
        self._allow_contains_default = True
        return return_value

    def keys(self):
        """Include the default keys, after the list of actually-set ones."""
        keys = list(self)
        for key in getattr(self, 'defaults_', []):
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
        """Include default keys"""
        for key in OrderedDict.iterkeys(self):
            yield key
        for key in getattr(self, 'defaults_', []):
            if not OrderedDict.__contains__(self, key):
                yield key

    def itervalues(self):
        """Include default values."""
        for k in self.iterkeys():
            yield self[k]

    def iteritems(self):
        """Include default key-value pairs."""
        for k in self.iterkeys():
            yield (k, self[k])

    def __contains__(self, key):
        if self._allow_contains_default:
            if key in getattr(self, "defaults_", {}):
                return True
        return OrderedDict.__contains__(self, key)

    def __nonzero__(self):
        """Include any default keys in the nonzero calculation."""
        return bool(self.keys())
