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
"""Unit Tests for cylc.flow.parsec.validate.ParsecValidator.coerce methods."""

from typing import List

import pytest
from pytest import approx, param

from cylc.flow.parsec.config import ConfigNode as Conf
from cylc.flow.parsec.OrderedDict import OrderedDictWithDefaults
from cylc.flow.parsec.exceptions import IllegalValueError
from cylc.flow.parsec.validate import (
    BroadcastConfigValidator,
    CylcConfigValidator as VDR,
    DurationFloat,
    ListValueError,
    IllegalItemError,
    ParsecValidator,
    parsec_validate
)


@pytest.fixture
def sample_spec():
    with Conf('myconf') as myconf:
        with Conf('section1'):
            Conf('value1', default='')
            Conf('value2', default='what?')
        with Conf('section2'):
            Conf('enabled', VDR.V_BOOLEAN)
        with Conf('section3'):
            Conf('title', default='default', options=['1', '2'])
            Conf(
                'amounts',
                VDR.V_INTEGER_LIST,
                default=[1, 2, 3],
                # options=[[1, 2, 3]]
            )
            with Conf('entries'):
                Conf('key')
                Conf('value')
        with Conf('<whatever>'):
            Conf('section300000', default='')
            Conf('ids', VDR.V_INTEGER_LIST)
    return myconf


@pytest.fixture
def validator_invalid_values():
    """
    Data provider or invalid values for parsec validator. All values must not
    be null (covered elsewhere), and not dict's.

    Possible invalid scenarios must include:

    - cfg[key] is a list AND a value is not in list of the possible values
    - OR
    - cfg[key] is not a list AND cfg[key] not in the list of possible values

    :return: a list with sets of tuples for the test parameters
    :rtype: list
    """

    values = []

    # variables reused throughout
    spec = None
    msg = None

    # set 1 (t, f, f, t)
    with Conf('base') as spec:
        Conf('value', VDR.V_INTEGER_LIST, default=1, options=[1, 2, 3, 4])
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "1, 2, 3"
    msg = None
    values.append((spec, cfg, msg))

    # set 2 (t, t, f, t)
    with Conf('base') as spec:
        Conf('value', VDR.V_INTEGER_LIST, default=1, options=[1, 2, 3, 4])
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "1, 2, 5"
    msg = '(type=option) value = [1, 2, 5]'
    values.append((spec, cfg, msg))

    # set 3 (f, f, t, f)
    with Conf('base') as spec:
        Conf('value', VDR.V_INTEGER, default=1, options=[2, 3, 4])
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "2"
    msg = None
    values.append((spec, cfg, msg))

    # set 4 (f, f, t, t)
    with Conf('base') as spec:
        Conf('value', VDR.V_INTEGER, default=1, options=[1, 2, 3, 4])
    cfg = OrderedDictWithDefaults()
    cfg['value'] = "5"
    msg = '(type=option) value = 5'
    values.append((spec, cfg, msg))

    return values


@pytest.fixture
def strip_and_unquote_list():
    return [
        [
            '"a,b", c, "d e"',  # input
            ["a,b", "c", "d e"]  # expected
        ],
        [
            'foo bar baz',  # input
            ["foo bar baz"]  # expected
        ],
        [
            '"a", \'b\', c',  # input
            ["a", "b", "c"]  # expected
        ],
        [
            'a b c, d e f',  # input
            ["a b c", "d e f"]  # expected
        ],
    ]


def test_list_value_error():
    keys = ['a,', 'b', 'c']
    value = 'a sample value'
    error = ListValueError(keys, value, "who cares")
    output = str(error)
    expected = '(type=list) [a,][b]c = a sample value - (who cares)'
    assert expected == output


def test_list_value_error_with_exception():
    keys = ['a,', 'b', 'c']
    value = 'a sample value'
    exc = Exception('test')
    error = ListValueError(keys, value, "who cares", exc)
    output = str(error)
    expected = '(type=list) [a,][b]c = a sample value - (test: who cares)'
    assert expected == output


def test_illegal_value_error():
    value_type = 'ClassA'
    keys = ['a,', 'b', 'c']
    value = 'a sample value'
    error = IllegalValueError(value_type, keys, value)
    output = str(error)
    expected = "(type=ClassA) [a,][b]c = a sample value"
    assert expected == output


def test_illegal_value_error_with_exception():
    value_type = 'ClassA'
    keys = ['a,', 'b', 'c']
    value = 'a sample value'
    exc = Exception('test')
    error = IllegalValueError(value_type, keys, value, exc)
    output = str(error)
    expected = "(type=ClassA) [a,][b]c = a sample value - (test)"
    assert expected == output


def test_illegal_item_error():
    keys = ['a,', 'b', 'c']
    key = 'a sample value'
    error = IllegalItemError(keys, key)
    output = str(error)
    expected = "[a,][b][c]a sample value"
    assert expected == output


def test_illegal_item_error_message():
    keys = ['a,', 'b', 'c']
    key = 'a sample value'
    message = "invalid"
    error = IllegalItemError(keys, key, message)
    output = str(error)
    expected = "[a,][b][c]a sample value - (invalid)"
    assert expected == output


def test_parsec_validator_invalid_key(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section1'] = OrderedDictWithDefaults()
    cfg['section1']['value1'] = '1'
    cfg['section1']['value2'] = '2'
    cfg['section22'] = 'abc'
    with pytest.raises(IllegalItemError):
        parsec_validator.validate(cfg, sample_spec)


def test_parsec_validator_invalid_key_no_spec(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section1'] = OrderedDictWithDefaults()
    cfg['section1']['value1'] = '1'
    cfg['section1']['value2'] = '2'
    cfg['section22'] = 'abc'
    # remove the user-defined section from the spec
    sample_spec._children = {
        key: value
        for key, value in sample_spec._children.items()
        if key != '__MANY__'
    }
    with pytest.raises(IllegalItemError):
        parsec_validator.validate(cfg, sample_spec)


def test_parsec_validator_invalid_key_with_many_spaces(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section1'] = OrderedDictWithDefaults()
    cfg['section1']['value1'] = '1'
    cfg['section1']['value2'] = '2'
    cfg['section  3000000'] = 'test'
    with pytest.raises(IllegalItemError) as cm:
        parsec_validator.validate(cfg, sample_spec)
        assert str(cm.exception) == "section  3000000 - (consecutive spaces)"


def test_parsec_validator_invalid_key_with_many_invalid_values(
        validator_invalid_values
):
    for spec, cfg, msg in validator_invalid_values:
        parsec_validator = ParsecValidator()
        if msg is not None:
            with pytest.raises(IllegalValueError) as cm:
                parsec_validator.validate(cfg, spec)
            assert msg == str(cm.value)
        else:
            # cylc.flow.parsec_validator.validate(cfg, spec)
            # let's use the alias `parsec_validate` here
            parsec_validate(cfg, spec)
            # TBD assertIsNotNone when 2.6+
            assert parsec_validator is not None


def test_parsec_validator_invalid_key_with_many_1(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section1'] = OrderedDictWithDefaults()
    cfg['section1']['value1'] = '1'
    cfg['section1']['value2'] = '2'
    cfg['section3000000'] = OrderedDictWithDefaults()
    parsec_validator.validate(cfg, sample_spec)
    # TBD assertIsNotNone when 2.6+
    assert parsec_validator is not None


def test_parsec_validator_invalid_key_with_many_2(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section3'] = OrderedDictWithDefaults()
    cfg['section3']['title'] = '1'
    cfg['section3']['entries'] = OrderedDictWithDefaults()
    cfg['section3']['entries']['key'] = 'name'
    cfg['section3']['entries']['value'] = "1, 2, 3, 4"
    parsec_validator.validate(cfg, sample_spec)
    # TBD assertIsNotNone when 2.6+
    assert parsec_validator is not None


def test_parsec_validator(sample_spec):
    parsec_validator = ParsecValidator()
    cfg = OrderedDictWithDefaults()
    cfg['section1'] = OrderedDictWithDefaults()
    cfg['section1']['value1'] = '1'
    cfg['section1']['value2'] = '2'
    cfg['section3'] = OrderedDictWithDefaults()
    cfg['section3']['title'] = None
    parsec_validator.validate(cfg, sample_spec)
    # TBD assertIsNotNone when 2.6+
    assert parsec_validator is not None

# --- static methods


def test_coerce_none_fails():
    with pytest.raises(AttributeError):
        ParsecValidator.coerce_boolean(None, [])
    with pytest.raises(AttributeError):
        ParsecValidator.coerce_float(None, [])
    with pytest.raises(AttributeError):
        ParsecValidator.coerce_int(None, [])


def test_coerce_boolean():
    """Test coerce_boolean."""
    validator = ParsecValidator()
    # The good
    for value, result in [
        ('True', True),
        (' True ', True),
        ('"True"', True),
        ("'True'", True),
        ('true', True),
        (' true ', True),
        ('"true"', True),
        ("'true'", True),
        ('False', False),
        (' False ', False),
        ('"False"', False),
        ("'False'", False),
        ('false', False),
        (' false ', False),
        ('"false"', False),
        ("'false'", False),
        ('', None),
        ('  ', None)
    ]:
        assert validator.coerce_boolean(value, ['whatever']) == result
    # The bad
    for value in [
        'None', ' Who cares? ', '3.14', '[]', '[True]', 'True, False'
    ]:
        with pytest.raises(IllegalValueError):
            validator.coerce_boolean(value, ['whatever'])


@pytest.mark.parametrize(
    'value, expected',
    [
        ('3', 3.0),
        ('9.80', 9.80),
        ('3.141592654', 3.141592654),
        ('"3.141592654"', 3.141592654),
        ("'3.141592654'", 3.141592654),
        ('-3', -3.0),
        ('-3.1', -3.1),
        ('0', 0.0),
        ('-0', -0.0),
        ('0.0', 0.0),
        ('1e20', 1.0e20),
        ('6.02e23', 6.02e23),
        ('-1.6021765e-19', -1.6021765e-19),
        ('6.62607004e-34', 6.62607004e-34),
    ]
)
def test_coerce_float(value: str, expected: float):
    """Test coerce_float."""
    assert (
        ParsecValidator.coerce_float(value, ['whatever']) == approx(expected)
    )


def test_coerce_float__empty():
    # not a number
    assert ParsecValidator.coerce_float('', ['whatever']) is None


@pytest.mark.parametrize(
    'value',
    ['None', ' Who cares? ', 'True', '[]', '[3.14]', '3.14, 2.72']
)
def test_coerce_float__bad(value: str):
    with pytest.raises(IllegalValueError):
        ParsecValidator.coerce_float(value, ['whatever'])


@pytest.mark.parametrize(
    'value, expected',
    [
        ('', []),
        ('3', [3.0]),
        ('2*3.141592654', [3.141592654, 3.141592654]),
        ('12*8, 8*12.0', [8.0] * 12 + [12.0] * 8),
        ('-3, -2, -1, -0.0, 1.0', [-3.0, -2.0, -1.0, -0.0, 1.0]),
        ('6.02e23, -1.6021765e-19, 6.62607004e-34',
         [6.02e23, -1.6021765e-19, 6.62607004e-34]),
    ]
)
def test_coerce_float_list(value: str, expected: List[float]):
    """Test coerce_float_list."""
    items = ParsecValidator.coerce_float_list(value, ['whatever'])
    assert items == approx(expected)


@pytest.mark.parametrize(
    'value',
    ['None', 'e, i, e, i, o', '[]', '[3.14]', 'pi, 2.72', '2*True']
)
def test_coerce_float_list__bad(value: str):
    with pytest.raises(IllegalValueError):
        ParsecValidator.coerce_float_list(value, ['whatever'])


@pytest.mark.parametrize(
    'value, expected',
    [
        ('0', 0),
        ('3', 3),
        ('-3', -3),
        ('-0', -0),
        ('653456', 653456),
        ('-8362583645365', -8362583645365)
    ]
)
def test_coerce_int(value: str, expected: int):
    """Test coerce_int."""
    assert ParsecValidator.coerce_int(value, ['whatever']) == expected


def test_coerce_int__empty():
    assert ParsecValidator.coerce_int('', ['whatever']) is None  # not a number


@pytest.mark.parametrize(
    'value',
    ['None', ' Who cares? ', 'True', '4.8', '[]', '[3]', '60*60']
)
def test_coerce_int__bad(value: str):
    with pytest.raises(IllegalValueError):
        ParsecValidator.coerce_int(value, ['whatever'])


def test_coerce_int_list():
    """Test coerce_int_list."""
    validator = ParsecValidator()
    # The good
    for value, results in [
        ('', []),
        ('3', [3]),
        ('1..10, 11..20..2',
         [1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 13, 15, 17, 19]),
        ('18 .. 24', [18, 19, 20, 21, 22, 23, 24]),
        ('18 .. 24 .. 3', [18, 21, 24]),
        ('-10..10..3', [-10, -7, -4, -1, 2, 5, 8]),
        ('10*3, 4*-6', [3] * 10 + [-6] * 4),
        ('10*128, -78..-72, 2048',
         [128] * 10 + [-78, -77, -76, -75, -74, -73, -72, 2048])
    ]:
        assert validator.coerce_int_list(value, ['whatever']) == results
    # The bad
    for value in [
        'None', 'e, i, e, i, o', '[]', '1..3, x', 'one..ten'
    ]:
        with pytest.raises(IllegalValueError):
            validator.coerce_int_list(value, ['whatever'])


@pytest.mark.parametrize(
    'value, expected',
    [
        ('', ''),
        ('Hello World!', 'Hello World!'),
        ('"Hello World!"', 'Hello World!'),
        ('"Hello Cylc\'s World!"', 'Hello Cylc\'s World!'),
        ("'Hello World!'", 'Hello World!'),
        ('0', '0'),
        ('My list is:\nfoo, bar, baz\n', 'My list is:\nfoo, bar, baz'),
        ('    Hello:\n    foo\n    bar\n    baz\n',
         'Hello:\nfoo\nbar\nbaz'),
        ('    Hello:\n        foo\n    Greet\n        baz\n',
         'Hello:\n    foo\nGreet\n    baz'),
        ('False', 'False'),
        ('None', 'None'),
        (['a', 'b'], 'a\nb'),
        ('abc#def', 'abc'),
    ]
)
def test_coerce_str(value: str, expected: str):
    """Test coerce_str."""
    validator = ParsecValidator()
    # The good
    assert validator.coerce_str(value, ['whatever']) == expected


def test_coerce_str_list():
    """Test coerce_str_list."""
    validator = ParsecValidator()
    # The good
    for value, results in [
        ('', []),
        ('Hello', ['Hello']),
        ('"Hello"', ['Hello']),
        ('1', ['1']),
        ('Mercury, Venus, Earth, Mars',
         ['Mercury', 'Venus', 'Earth', 'Mars']),
        ('Mercury, Venus, Earth, Mars,\n"Jupiter",\n"Saturn"\n',
         ['Mercury', 'Venus', 'Earth', 'Mars', 'Jupiter', 'Saturn']),
        ('New Zealand, United Kingdom',
         ['New Zealand', 'United Kingdom'])
    ]:
        assert validator.coerce_str_list(value, ['whatever']) == results


@pytest.mark.parametrize('value, expected', [
    param(
        "'a'",
        'a',
        id="single quotes"
    ),
    param(
        '"\'a\'"',
        "'a'",
        id="single quotes inside double quotes"
    ),
    param(
        '" a b" # comment',
        ' a b',
        id="comment outside"
    ),
    param(
        '"""bene\ngesserit"""',
        'bene\ngesserit',
        id="multiline double quotes"
    ),
    param(
        "'''kwisatz\n  haderach'''",
        'kwisatz\n  haderach',
        id="multiline single quotes"
    ),
    param(
        '"""a\nb"""  # comment',
        'a\nb',
        id="multiline with comment outside"
    ),
])
def test_unquote(value: str, expected: str):
    """Test strip_and_unquote."""
    assert ParsecValidator._unquote(['a'], value) == expected


@pytest.mark.parametrize('value', [
    '"""',
    "'''",
    "'don't do this'",
])
def test_strip_and_unquote__bad(value: str):
    with pytest.raises(IllegalValueError):
        ParsecValidator.strip_and_unquote(['a'], value)


def test_strip_and_unquote_list_parsec():
    """Test strip_and_unquote_list using ParsecValidator."""
    for value, results in [
        ('"a"\n"b"', ['a', 'b']),
        ('"a", "b"', ['a', 'b']),
        ('"a", "b"', ['a', 'b']),
        ('"c" # d', ['c']),
        ('"a", "b", "c" # d', ['a', 'b', 'c']),
        ('"a"\n"b"\n"c" # d', ['a', 'b', 'c']),
        ("'a', 'b'", ['a', 'b']),
        ("'c' #d", ['c']),
        ("'a', 'b', 'c' # d", ['a', 'b', 'c']),
        ("'a'\n'b'\n'c' # d", ['a', 'b', 'c']),
        ('a, b, c,', ['a', 'b', 'c']),
        ('a, b, c # d', ['a', 'b', 'c']),
        ('a, b, c\n"d"', ['a', 'b', 'd']),
        ('a, b, c\n"d" # e', ['a', 'b', '"d"'])
    ]:
        assert results == ParsecValidator.strip_and_unquote_list(
            ['a'], value)


def test_strip_and_unquote_list_cylc(strip_and_unquote_list):
    """Test strip_and_unquote_list using CylcConfigValidator."""
    validator = VDR()
    for values in strip_and_unquote_list:
        value = values[0]
        expected = values[1]
        output = validator.strip_and_unquote_list(keys=[], value=value)
        assert expected == output


def test_strip_and_unquote_list_multiparam():
    with pytest.raises(ListValueError):
        ParsecValidator.strip_and_unquote_list(
            ['a'], 'a, b, c<a,b>'
        )


def test_coerce_cycle_point():
    """Test coerce_cycle_point."""
    validator = VDR()
    # The good
    for value, result in [
            ('', None),
            ('3', '3'),
            ('2018', '2018'),
            ('20181225T12Z', '20181225T12Z'),
            ('2018-12-25T12:00+11:00', '2018-12-25T12:00+11:00')]:
        assert validator.coerce_cycle_point(value, ['whatever']) == result
    # The bad
    for value in [
            'None', ' Who cares? ', 'True', '1, 2', '20781340E10']:
        with pytest.raises(IllegalValueError):
            validator.coerce_cycle_point(value, ['whatever'])


def test_coerce_cycle_point_format():
    """Test coerce_cycle_point_format."""
    validator = VDR()
    # The good
    for value, result in [
            ('', None),
            ('%Y%m%dT%H%M%z', '%Y%m%dT%H%M%z'),
            ('CCYYMMDDThhmmZ', 'CCYYMMDDThhmmZ'),
            ('XCCYYMMDDThhmmZ', 'XCCYYMMDDThhmmZ')]:
        assert (
            validator.coerce_cycle_point_format(value, ['whatever'])
            == result
        )
    # The bad
    # '/' and ':' not allowed in cylc cycle points (they are used in paths).
    for value in ['%i%j', 'Y/M/D', '%Y-%m-%dT%H:%MZ']:
        with pytest.raises(IllegalValueError):
            validator.coerce_cycle_point_format(value, ['whatever'])


def test_coerce_cycle_point_time_zone():
    """Test coerce_cycle_point_time_zone."""
    validator = VDR()
    # The good
    for value, result in [
            ('', None),
            ('Z', 'Z'),
            ('+0000', '+0000'),
            ('+0100', '+0100'),
            ('+1300', '+1300'),
            ('-0630', '-0630')]:
        assert (
            validator.coerce_cycle_point_time_zone(value, ['whatever'])
            == result
        )
    # The bad
    for value in ['None', 'Big Bang Time', 'Standard Galaxy Time']:
        with pytest.raises(IllegalValueError):
            validator.coerce_cycle_point_time_zone(value, ['whatever'])


def test_coerce_interval():
    """Test coerce_interval."""
    validator = VDR()
    # The good
    for value, result in [
            ('', None),
            ('P3D', DurationFloat(259200)),
            ('PT10M10S', DurationFloat(610))]:
        assert validator.coerce_interval(value, ['whatever']) == result
    # The bad
    for value in ['None', '5 days', '20', '-12']:
        with pytest.raises(IllegalValueError):
            validator.coerce_interval(value, ['whatever'])


@pytest.mark.parametrize(
    'value, expected',
    [
        ('', []),
        ('P3D', [DurationFloat(259200)]),
        ('P3D, PT10M10S', [DurationFloat(259200), DurationFloat(610)]),
        ('25*PT30M,10*PT1H',
         [DurationFloat(1800)] * 25 + [DurationFloat(3600)] * 10)
    ]
)
def test_coerce_interval_list(value: str, expected: List[DurationFloat]):
    """Test coerce_interval_list."""
    assert VDR.coerce_interval_list(value, ['whatever']) == approx(expected)


@pytest.mark.parametrize(
    'value',
    ['None', '5 days', '20', 'PT10S, -12']
)
def test_coerce_interval_list__bad(value: str):
    with pytest.raises(IllegalValueError):
        VDR.coerce_interval_list(value, ['whatever'])


def test_coerce_parameter_list():
    """Test coerce_parameter_list."""
    validator = VDR()
    # The good
    for value, result in [
            ('', []),
            ('planet', ['planet']),
            ('planet, star, galaxy', ['planet', 'star', 'galaxy']),
            ('1..5, 21..25', [1, 2, 3, 4, 5, 21, 22, 23, 24, 25]),
            ('-15, -10, -5, -1..1', [-15, -10, -5, -1, 0, 1])]:
        assert validator.coerce_parameter_list(value, ['whatever']) == result
    # The bad
    for value in ['foo/bar', 'p1, 1..10', '2..3, 4, p']:
        with pytest.raises(IllegalValueError):
            validator.coerce_parameter_list(value, ['whatever'])


def test_coerce_xtrigger():
    """Test coerce_xtrigger."""
    validator = VDR()
    # The good
    for value, result in [
            ('foo(x="bar")', 'foo(x=bar)'),
            ('foo(x, y, z="zebra")', 'foo(x, y, z=zebra)')]:
        assert (
            validator.coerce_xtrigger(value, ['whatever']).get_signature()
            == result
        )
    # The bad
    for value in [
            '', 'foo(', 'foo)', 'foo,bar']:
        with pytest.raises(IllegalValueError):
            validator.coerce_xtrigger(value, ['whatever'])


def test_type_help_examples():
    types = {
        **ParsecValidator.V_TYPE_HELP,
        **VDR.V_TYPE_HELP
    }

    validator = VDR()

    for vdr, info in types.items():
        coercer = validator.coercers[vdr]
        if len(info) > 2:
            for example in info[2]:
                try:
                    coercer(example, [None])
                except Exception:
                    raise Exception(
                        f'Example "{example}" failed for type "{vdr}"')


@pytest.mark.parametrize('value, expected', [
    param(
        """
        a="don't have a cow"
        a=${a#*have}
        echo "$a" # let's see what happens
        """,
        "a=\"don't have a cow\"\na=${a#*have}\necho \"$a\" # let's see what happens",
        id="multiline"
    ),
    param(
        '"sleep 30 # ja!"  ',
        'sleep 30 # ja!',
        id="quoted"
    ),
])
def test_broadcast_coerce_str(value: str, expected: str):
    assert BroadcastConfigValidator.coerce_str(value, ['whatever']) == expected
