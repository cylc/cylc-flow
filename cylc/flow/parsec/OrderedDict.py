# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
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

"""Ordered Dictionary data structure used extensively in cylc."""


from collections import OrderedDict


class OrderedDictWithDefaults(OrderedDict):

    """Subclass to provide defaults fetching capability."""

    # Note that defining a '__missing__' method would work for foo[key],
    # but doesn't for foo.get(key).

    def __init__(self, *args, **kwargs):
        """Allow a defaults argument."""
        self._allow_contains_default = True
        super().__init__(*args, **kwargs)

    def __getitem__(self, key):
        # Override to look in our special defaults attribute, if it exists.
        try:
            return OrderedDict.__getitem__(self, key)
        except KeyError:
            if hasattr(self, 'defaults_'):
                return self.defaults_[key]
            raise

    def __setitem__(self, *args, **kwargs):
        # Make sure that we don't set the default value!
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
        yield from OrderedDict.keys(self)
        for key in getattr(self, 'defaults_', []):
            if not OrderedDict.__contains__(self, key):
                yield key

    def itervalues(self):
        """Include default values."""
        for k in self.keys():
            yield self[k]

    def iteritems(self):
        """Include default key-value pairs."""
        for k in self.keys():
            yield (k, self[k])

    def __contains__(self, key):
        if (
            self._allow_contains_default
            and key in getattr(self, "defaults_", {})
        ):
            return True
        return OrderedDict.__contains__(self, key)

    def __bool__(self):
        """Include any default keys in the nonzero calculation."""
        return bool(list(self.keys()))

    def prepend(self, key, value):
        """Prepend new item in the ordered dict."""
        # https://stackoverflow.com/questions/16664874/
        #   how-can-i-add-an-element-at-the-top-of-an-ordereddict-in-python
        self[key] = value
        self.move_to_end(key, last=False)

    @staticmethod
    def repl_val(target, replace, replacement):
        """Replace dictionary values with a string.

        Designed to be used recursively.
        """
        for key, val in target.items():
            if isinstance(val, dict):
                OrderedDictWithDefaults.repl_val(
                    val, replace, replacement)
            elif val == replace:
                target[key] = replacement


class DictTree:
    """An object providing a single point of access to a tree of dicts.

    * Allows easy extraction of values from a collection of dictionaries.
    * Values from dictionaries earlier in the list will take priority over
      values from dictionaries later in the list.
    * If the dict objects provided provide a custom `get` interface this
      will take priority over the `__getitem__` interface.

    Args:
        tree (list):
            A list of dict-type objects.

    Examples:
        Regular usage:
        >>> tree = DictTree(
        ...     {'a': 1, 'b': 2},
        ...     {'b': 3, 'c': 4}
        ... )
        >>> tree['a']
        1
        >>> tree['b']  # items from earlier entries are preferred
        2
        >>> tree['c']
        4
        >>> tree['d']
        Traceback (most recent call last):
        KeyError: 'd'

        Quirk, None values result in KeyErrors:
        >>> tree = DictTree({'a': None})
        >>> tree['a']
        Traceback (most recent call last):
        KeyError: 'a'

    """

    def __init__(self, *tree):
        self._tree = tree

    def __getitem__(self, key):
        values = []
        defaults = []
        for branch in self._tree:
            # priority goes to the `get` method
            value = branch.get(key)
            if value is not None:
                values.append(value)
                defaults.append(None)
            else:
                try:
                    # then falls back to the `__getitem__` method
                    defaults.append(branch[key])
                    values.append(None)
                except KeyError:
                    # okay, this key really isn't present here
                    values.append(None)
                    defaults.append(None)

        # handle nested dictionaries
        if any((isinstance(item, dict) for item in values + defaults)):
            return DictTree(*(
                item
                for item in values
                if item is not None
            ))

        # handle non-existent keys
        if all((item is None for item in values + defaults)):
            raise KeyError(key)

        # return first value or default encountered
        return next((
            item
            for item in values + defaults
            if item is not None
        ))

    def __eq__(self, other):
        if not isinstance(other, DictTree):
            return False
        return self._tree == other._tree

    def __iter__(self):
        def inner(tree):
            # yield keys from all branches (but only once)
            yield from {
                key
                for branch in tree
                for key in branch
            }
        return inner(self._tree)

    def get(self, key, default=None):
        """Get an item from this tree or return `default` if not present.

        Note:
            Behaviour purposefully differs from OrderedDictWithDefaults,
            this `get` method *will* return default values if present.

        """
        try:
            return self[key]
        except KeyError:
            return default
