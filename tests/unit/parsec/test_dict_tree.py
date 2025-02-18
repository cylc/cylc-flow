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

from cylc.flow.parsec.OrderedDict import (
    DictTree,
    OrderedDictWithDefaults as ODD
)

import pytest


def test_eq():
    """It compares to identical instances."""
    assert DictTree({'a': 1}) == DictTree({'a': 1})
    assert DictTree({'a': 1}) != DictTree({'a': 2})
    assert DictTree({'a': 1}) != {'a': 1}


def test_nesting():
    """It slices without duplicating data."""
    this_a = {'b': 1}
    this = {'a': this_a}
    that_a = {'b': 2}
    that = {'a': that_a}
    both = DictTree(this, that)

    sub = both['a']
    assert sub._tree == (this_a, that_a)
    r_this_a, r_that_a = sub._tree
    assert id(r_this_a) == id(this_a)
    assert id(r_that_a) == id(that_a)


def test_iter():
    """It yields keys from all dictionaries."""
    a = DictTree({'a': 1}, {'a': 2, 'b': 3})
    assert sorted(a) == ['a', 'b']


def test_iter_defaults():
    """It doesn't yield keys from defaults."""
    this = ODD(a=1)
    that = ODD(b=2)
    this.defaults = {'c': 3}
    that.defaults = {'d': 4}
    a = DictTree(this, that)
    assert sorted(a) == ['a', 'b']


def test_getitem():
    """It returns values prioritised correctly via the `getitem` interface."""
    this = {
        'a': 1,
        'b': 2,
        'f': {
            'x': 5,
            'y': 6
        }
    }
    that = {
        'b': 3,
        'd': 4,
        'f': {
            'y': 7,
            'z': 8
        }
    }
    a = DictTree(this, that)

    # key from this
    assert a['a'] == 1
    # key from that
    assert a['d'] == 4
    # key from this overrides key from that
    assert a['b'] == 2

    # dict from both
    f = a['f']
    assert f._tree == (this['f'], that['f'])
    assert f['x'] == 5  # key from this
    assert f['y'] == 6  # key from this which is also in that
    assert f['z'] == 8  # key from that

    # mutate definition object
    this['f']['y'] = 42
    assert a['f']['y'] == 42


def test_get():
    """It returns values correctly via the `get` interface."""
    a = DictTree({'a': 1}, {'b': 2})

    # key exists in this
    assert a.get('a') == 1
    assert a.get('a', 42) == 1
    # key exists in that
    assert a.get('b') == 2
    assert a.get('b', 42) == 2
    # key does not exist
    assert a.get('e') is None
    assert a.get('e', 42) == 42


def test_get_dict():
    """It slices correctly via the `get` interface."""
    a = DictTree({'a': {'b': 1}}, {'a': {'b': 2}})
    assert a.get('a') == DictTree({'b': 1}, {'b': 2})


def test_odd_getitem():
    """It returns default values if none of the dicts contains the key."""
    this = ODD(a=1)
    this.defaults_ = {'c': 3}
    that = ODD(b=2)
    that.defaults_ = {'d': 4}
    both = DictTree(this, that)

    # key from this
    assert both['a'] == 1
    # key from that
    assert both['b'] == 2
    # default from this
    assert both['c'] == 3
    # default from that
    assert both['d'] == 4
    # missing value
    with pytest.raises(KeyError):
        both['e']


def test_defaults_getitem_dict():
    """It returns defaults if a value isn't set."""
    this = ODD()
    that = ODD(a=2)
    both = DictTree(this, that)

    # default in this gets overridden by value in that
    this.defaults_ = {'a': 1}
    that.defaults_ = {}
    assert both['a'] == 2

    # default in first dict gets priority
    this.defaults_ = {'b': 1}
    that.defaults_ = {'b': 2}
    assert both['b'] == 1


def test_defaults_getitem_nested():
    """It preserves the defaults_ behaviour of ODD in nested dicts."""
    this = ODD()
    that = ODD(a=2)
    both = DictTree({'a': this}, {'a': that})

    # default in this gets overridden by value in that
    this.defaults_ = {'a': 1}
    that.defaults_ = {}
    assert both['a']['a'] == 2

    # default in first dict gets priority
    this.defaults_ = {'b': 1}
    that.defaults_ = {'b': 2}
    assert both['a']['b'] == 1
