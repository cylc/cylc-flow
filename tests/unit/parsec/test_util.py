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

from io import StringIO

import pytest

from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.util import (
    SECTION_EXPAND_PATTERN,
    expand_many_section,
    itemstr,
    listjoin,
    m_override,
    pdeepcopy,
    poverride,
    printcfg,
    replicate,
    un_many,
)


def test_listjoin():
    assert listjoin(None) == ''
    assert listjoin(None, 'test') == 'test'
    assert listjoin([], 'test') == 'test'
    assert listjoin([None], 'test') == 'test'
    assert listjoin(['test', 'test']) == 'test, test'
    assert listjoin(['test,', 'test']) == '\'test,\', test'


# --- printcfg

def test_printcfg():
    cfg = OrderedDictWithDefaults()
    cfg['root'] = OrderedDictWithDefaults()
    cfg['root']['special'] = 1
    cfg['root']['normal'] = 0
    cfg['root'][None] = None
    cfg[None] = None

    myhandle = StringIO()
    printcfg(cfg, handle=myhandle)
    expected = "\n[root]\n    special = 1\n    normal = 0\n    \n"
    actual = myhandle.getvalue()
    assert actual == expected


def test_printcfg_none_str_is_none():
    cfg = OrderedDictWithDefaults()
    cfg['root'] = OrderedDictWithDefaults()
    cfg['root']['special'] = 1
    cfg['root']['normal'] = 0
    cfg['root'][None] = None
    cfg[None] = None

    myhandle = StringIO()
    printcfg(cfg, handle=myhandle, none_str=None)
    expected = "[root]\n    special = 1\n    normal = 0\n"
    actual = myhandle.getvalue()
    assert actual == expected


def test_printcfg_list_values():
    cfg = OrderedDictWithDefaults()
    cfg['root'] = OrderedDictWithDefaults()
    cfg['root']['special'] = ['a', 'b', 'c', None]
    cfg['root']['normal'] = 0

    myhandle = StringIO()
    printcfg(cfg, handle=myhandle, none_str='d')
    expected = "[root]\n    special = a, b, c, d\n    normal = 0\n"
    actual = myhandle.getvalue()
    assert actual == expected


def test_printcfg_break_lines():
    cfg = OrderedDictWithDefaults()
    cfg['root'] = OrderedDictWithDefaults()
    cfg['root']['special'] = "\nthis is\nvalid"
    cfg['root']['normal'] = 0

    myhandle = StringIO()
    printcfg(cfg, handle=myhandle)
    expected = (
        "[root]\n    special = \"\"\"\n        \n    "
        "    this is\n        valid\n    \"\"\"\n    normal = 0\n"
    )
    actual = myhandle.getvalue()
    assert actual == expected


# --- replicate

def test_replicate():
    replicate('Name', None)  # does nothing, no exception/error
    source_1 = OrderedDictWithDefaults()
    source_1["name"] = "sea"
    source_1["origin"] = "kitchen"
    source_1.defaults_ = {"brewery": False}
    source_2 = OrderedDictWithDefaults()
    source_2["name"] = ["sea", "legume"]
    source_2["origin"] = "fridge"
    source_3 = OrderedDictWithDefaults()
    source_3["name"] = OrderedDictWithDefaults()
    source_3["name"]["value"] = "oil"
    source_3["name"]["key"] = 1
    source_3["name"].defaults_ = {"value": 1}

    target_1 = OrderedDictWithDefaults()
    target_2 = OrderedDictWithDefaults()
    target_3 = OrderedDictWithDefaults()

    replicate(target_1, source_1)
    replicate(target_2, source_2)
    replicate(target_3, source_3)

    # Note: assertDictEqual not available for Python 2.6
    assert str(target_1) == str(source_1)
    assert str(target_2) == str(source_2)
    assert str(target_3) == str(source_3)


# --- pdeepcopy

def test_pdeepcopy():
    """This is tested entirely by the tests in replicate as well"""
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["value"] = "oil"
    source["name"]["key"] = 1
    source["name"].defaults_ = {"value": 1}

    target = pdeepcopy(source)

    assert target == source


# --- poverride

def test_poverride_append():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["value"] = "oil"
    source["name"]["key"] = [1, 2, 3, 4]

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    poverride(target, None)  # harmless, and no error/exception

    poverride(target, source)

    expected = OrderedDictWithDefaults()
    expected["index"] = 0
    expected["value"] = "oil"
    expected["key"] = [1, 2, 3, 4]

    assert target["name"] == expected


def test_poverride_prepend():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["value"] = "oil"
    source["name"]["key"] = [1, 2, 3, 4]

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    poverride(target, None)  # harmless, and no error/exception

    poverride(target, source, prepend=True)

    expected = OrderedDictWithDefaults()
    expected["key"] = [1, 2, 3, 4]
    expected["value"] = "oil"
    expected["index"] = 0

    assert target["name"] == expected


# -- m_override

def test_m_override():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["index"] = "oil"
    source["name2"] = OrderedDictWithDefaults()
    source["name2"]["key"] = [1, 2, 3, 4]
    source["name2"]["text"] = ""
    source["name2"]["subdict"] = OrderedDictWithDefaults()
    source["name2"]["subdict"]['family'] = 'ALL'

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict']['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict']['__MANY__']['family'] = 'LATIN'
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    assert target["name"]["index"] == 0
    m_override(target, source)
    assert target["name"]["index"] == "oil"


def test_m_override_many_with_many():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["index"] = "oil"
    source["name2"] = OrderedDictWithDefaults()
    source["name2"]["key"] = [1, 2, 3, 4]
    source["name2"]["text"] = ""
    source["name2"]["subdict"] = OrderedDictWithDefaults()
    source["name2"]["subdict"]['family'] = 'ALL'

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict']['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict']['__MANY__']['family'] = 'LATIN'
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    # code is OK until here

    # It appears this is valid for now, but may change later
    target['__MANY__']['__MANY__'] = OrderedDictWithDefaults()

    with pytest.raises(Exception):
        m_override(target, source)


def test_m_override_without_many_1():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["value"] = "oil"
    source["name"]["key"] = [1, 2, 3, 4]

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0

    with pytest.raises(Exception):
        m_override(target, source)


def test_m_override_without_many_2():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["index"] = "oil"
    source["name2"] = OrderedDictWithDefaults()
    source["name2"]["key"] = [1, 2, 3, 4]

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    # target['__MANY__']['key'] = []

    with pytest.raises(Exception):
        m_override(target, source)


def test_m_override_without_many_3():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["index"] = "oil"
    source["name2"] = OrderedDictWithDefaults()
    source["name2"]["key"] = [1, 2, 3, 4]
    source["name2"]["text"] = ""
    source["name2"]["subdict"] = OrderedDictWithDefaults()
    source["name2"]["subdict"]['family'] = 'ALL'

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict'] = OrderedDictWithDefaults()
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    with pytest.raises(Exception):
        m_override(target, source)


def test_m_override_without_many_4():
    source = OrderedDictWithDefaults()
    source["name"] = OrderedDictWithDefaults()
    source["name"]["index"] = "oil"
    source["name2"] = OrderedDictWithDefaults()
    source["name2"]["key"] = [1, 2, 3, 4]
    source["name2"]["text"] = ""
    source["name2"]["subdict"] = OrderedDictWithDefaults()
    source["name2"]["subdict"]['family'] = 'ALL'

    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    with pytest.raises(Exception):
        m_override(target, source)


# --- un_many

def test_un_many():
    target = OrderedDictWithDefaults()
    target["name"] = OrderedDictWithDefaults()
    target["name"]["index"] = 0
    target['__MANY__'] = OrderedDictWithDefaults()
    target['__MANY__']['name2'] = OrderedDictWithDefaults()
    target['__MANY__']['subdict'] = OrderedDictWithDefaults()
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    un_many(None)  # harmless, no error/exception

    un_many(target)

    assert '__MANY__' not in list(target)


def test_un_many_keyerror():
    """
    Only way that this may happen is if dict is updated elsewhere.
    """
    class MyODWD(OrderedDictWithDefaults):
        def __delitem__(self, _):
            raise KeyError()

    target = MyODWD()
    target["name"] = "Anything"
    target.defaults_ = {}
    target.defaults_["name"] = True
    target.defaults_["__MANY__"] = True
    target['__MANY__'] = MyODWD()
    target['__MANY__']['name2'] = MyODWD()
    target['__MANY__']['subdict'] = MyODWD()
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    un_many(None)  # harmless, no error/exception
    un_many(target)

    assert target
    assert '__MANY__' in target


def test_un_many_keyerror_no_default():
    """
    Only way that this may happen is if dict is updated elsewhere.

    And in this case, when there is no defaults_, the API raises the
    current KeyError.
    """
    class MyODWD(OrderedDictWithDefaults):
        def __delitem__(self, _):
            raise KeyError()

    target = MyODWD()
    target["name"] = "Anything"
    target['__MANY__'] = MyODWD()
    target['__MANY__']['name2'] = MyODWD()
    target['__MANY__']['subdict'] = MyODWD()
    target['__MANY__']['key'] = []
    target['__MANY__']['text'] = "Ad infinitum"

    un_many(None)  # harmless, no error/exception

    with pytest.raises(KeyError):
        un_many(target)

# --- itemstr


def test_itemstr():
    parents = ["parent1", "parent2"]
    text = itemstr(parents=parents, item="Value", value="Anything")
    assert text == '[parent1][parent2]Value = Anything'


def test_itemstr_no_item():
    parents = ["parent1", "parent2", "Value"]
    text = itemstr(parents=parents, item=None, value="Anything")
    assert text == '[parent1][parent2]Value = Anything'


def test_itemstr_no_parents_no_item():
    text = itemstr(parents=None, item=None, value='Anything')
    assert text == 'Anything'


def test_itemstr_no_parents():
    text = itemstr(parents=None, item="Value", value='Anything')
    assert text == 'Value = Anything'


def test_itemstr_no_parents_no_value():
    text = itemstr(parents=None, item="Value", value=None)
    assert text == 'Value'


# --- expand_many_section

@pytest.mark.parametrize(
    'in_,out',
    [
        # basically a fancy version of string.split(',')
        ('foo', ['foo']),
        ('foo,bar', ['foo', 'bar']),
        ('foo, bar', ['foo', ' bar']),  # doesn't remove whitespace
        # except that it doesn't split quoted things
        ('"foo", "bar"', ['"foo"', ' "bar"']),
        ('"foo,", "b,ar"', ['"foo,"', ' "b,ar"']),  # doesn't split in " quotes
        ("'foo', 'bar'", ["'foo'", " 'bar'"]),
        ("'foo,', 'b,ar'", ["'foo,'", " 'b,ar'"]),  # doesn"t split in ' quotes
    ]
)
def test_SECTION_EXPAND_PATTERN(in_, out):
    """It should split sections which contain commas.

    This is used in order to expand [foo, bar] into [foo] and [bar].
    """
    assert SECTION_EXPAND_PATTERN.findall(in_) == out


@pytest.mark.parametrize(
    'in_,out',
    [
        ('foo,bar', ['foo', 'bar']),
        ('foo , bar', ['foo', 'bar']),
        ('"foo", "bar"', ['foo', 'bar']),
        ('"foo,", "b,ar"', ['foo,', 'b,ar']),
    ]
)
def test_expand_many_section_expand(in_, out):
    """It should expand sections which contain commas.

    E.G. it should expand [foo, bar] into [foo] and [bar].
    """
    config = {in_: {'whatever': True}}
    assert list(expand_many_section(config)) == out


def test_expand_many_section_order():
    """It should maintain order when expanding sections."""
    assert list(expand_many_section({
        'a': {},
        'b, a': {},
        'c, b, a, d': {},
        'e': {},
        'a, e': {},
        'f, e': {},
        'g, h': {},
    })) == ['a', 'b', 'c', 'd', 'e', 'f', 'g', 'h']


def test_expand_many_section_merge():
    """It should merge sections together in definition order."""
    config = expand_many_section({
        'b': {'x': 1},
        'b, a, c, d': {'x': 2},
        'c': {'x': 3},
    })
    assert config == {
        'b': {'x': 2},
        'a': {'x': 2},
        'c': {'x': 3},
        'd': {'x': 2},
    }
    # bonus marks: ensure all values copied rather than referenced
    config['a']['x'] = 4
    assert config['b']['x'] == 2


def test_expand_many_section_merge_deep():
    """It should deep-merge nested sections - see replicate()."""
    config = expand_many_section({
        'b': {'x': {'y': 1}},
        'b, a, c, d': {'x': {'y': 2}},
        'c': {'x': {'y': 3}},
    })
    assert config == {
        'b': {'x': {'y': 2}},
        'a': {'x': {'y': 2}},
        'c': {'x': {'y': 3}},
        'd': {'x': {'y': 2}},
    }
    # bonus marks: ensure all values are unique objects
    # (i.e. they have been copied rather than referenced)
    config['a']['x']['y'] = 4
    assert config['b']['x']['y'] == 2
