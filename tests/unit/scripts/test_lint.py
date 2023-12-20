#!/usr/bin/env python3
# THIS FILE IS PART OF THE CYLC WORKFLOW ENGINE.
# Copyright (C) NIWA & British Crown (Met Office) & Contributors.
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.

# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
"""Tests `cylc lint` CLI Utility."""

from pathlib import Path
from pprint import pformat
import re
from types import SimpleNamespace

import pytest
from pytest import param

from cylc.flow.scripts.lint import (
    MANUAL_DEPRECATIONS,
    get_cylc_files,
    get_pyproject_toml,
    get_reference,
    get_upgrader_info,
    lint,
    _merge_cli_with_tomldata,
    parse_checks,
    validate_toml_items
)
from cylc.flow.exceptions import CylcError

STYLE_CHECKS = parse_checks(['style'])
UPG_CHECKS = parse_checks(['728'])

TEST_FILE = """
[visualization]

[cylc]
    include at start-up = foo
    exclude at start-up = bar
    reset timer = false
    log resolved dependencies = True
    required run mode = False
    health check interval = PT10M
    abort if any task fails = true
    suite definition directory = '/woo'
    disable automatic shutdown = false
    spawn to max active cycle points = false
    [[reference test]]
        allow task failures = true
    [[simulation]]
        disable suite event handlers = true
    [[authentication]]
    [[environment]]
    force run mode = dummy
    [[events]]
        reset inactivity timer = 42
        abort on stalled = True
        abort on timeout = False
        abort if startup handler fails= True  # deliberately not added a space.
        abort if shutdown handler fails= True
        abort if timeout handler fails = True
        abort if stalled handler fails = True
        abort if inactivity handler fails = False
        aborted handler = woo
        stalled handler = bar
        timeout handler = bas
        shutdown handler = qux
        startup handler = now
        inactivity handler = bored
        mail to = eleanor.rigby@beatles.lv
        mail from = fr.mckenzie@beatles.lv
        mail footer = "Collecting The Rice"
        mail smtp = 123.456.789.10
        timeout = 30
        inactivity = 30
        abort on inactivity = 30
    [[parameters]]
    [[parameter templates]]
    [[mail]]
        task event mail interval    = PT4M # deliberately added lots of spaces.

[scheduling]
    max active cycle points = 5
    hold after point = 20220101T0000Z
    [[dependencies]]
        [[[R1]]]
            graph = MyFaM:finish-all => remote => !mash_theme

[runtime]
    [[root]]
        [[[environment]]]
            CYLC_VERSION={{CYLC_VERSION}}
            ROSE_VERSION  = {{ROSE_VERSION     }}
            FCM_VERSION = {{   FCM_VERSION   }}

    [[MyFaM]]
        extra log files = True
        {% from 'cylc.flow' import LOG %}
        pre-script = "echo ${CYLC_SUITE_DEF_PATH}"
        script = {{HELLOWORLD}}
        post-script = "echo ${CYLC_SUITE_INITIAL_CYCLE_TIME}"
        env-script = POINT=$(rose  date 2059 --offset P1M)
        [[[suite state polling]]]
            template = and
        [[[remote]]]
            host = parasite
            suite definition directory = '/home/bar'
        [[[job]]]
            batch system = slurm
            shell = fish
        [[[events]]]
            mail retry delays = PT30S
            warning handler = frr.sh
            submission timeout handler = faiuhdf
            submission retry handler = vhbayhrbfgau
            submission failed handler = giaSEHFUIHJ
            failed handler = woo
            execution timeout handler = sdfghjkl
            expired handler = %(suite_uuid)s %(user@host)s
            late handler = dafuhj
            submitted handler = dafuhj
            started handler = dafuhj
            succeeded handler = dafuhj
            custom handler = efrgh
            critical handler = fgjdsfs
            retry handler = dfaiuhfrgpa
            sumbission handler = fas9hrfgaiuph

# Shouldn't object to a comment, unlike the terrible indents below:
   [[bad indent]]
        inherit = MyFaM

     [[remote]]
        platform = $(rose host-select parasite)
        script = "cylc nudge"
        post-script = "rose suite-hook"

 [meta]
    [[and_another_thing]]
        [[[remote]]]
            host = `rose host-select thingy`
"""


LINT_TEST_FILE = """
\t[scheduler]

 [scheduler]

[[dependencies]]
{% set   N = 009 %}
{% foo %}
{{foo}}
# {{quix}}

[runtime]
    [[this_is_ok]]
      script = echo "this is incorrectly indented"

          [[foo]]
        inherit = hello
     [[[job]]]
something\t
    [[bar]]
        platform = $(some-script foo)
    [[baz]]
        platform = `no backticks`
""" + (
    '\nscript = the quick brown fox jumps over the lazy dog until it becomes '
    'clear that this line is longer than the default 130 character limit.'
)


def lint_text(text, checks, ignores=None, modify=False):
    checks = parse_checks(checks, ignores)
    counter = {}
    messages = []
    outlines = [
        line
        for line in lint(
            Path('flow.cylc'),
            iter(text.splitlines()),
            checks,
            counter,
            modify=modify,
            write=messages.append
        )
    ]
    return SimpleNamespace(
        counter=counter,
        messages=messages,
        outlines=outlines
    )


def filter_strings(items, contains):
    """Return only items which contain a given string."""
    return [
        message
        for message in items
        if contains in message
    ]


def assert_contains(items, contains, instances=None):
    """Pass if at least one item contains a given string."""
    filtered = filter_strings(items, contains)
    if not filtered:
        raise Exception(
            f'Could not find: "{contains}" in:\n'
            + pformat(items))
    elif instances and len(filtered) != instances:
        raise Exception(
            f'Expected "{contains}" to appear {instances} times'
            f', got it {len(filtered)} times.')


EXPECT_INSTANCES_OF_ERR = {
    16: 3,
}


@pytest.mark.parametrize(
    # 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(MANUAL_DEPRECATIONS) + 1)) - {11}
)
def test_check_cylc_file_7to8(number):
    """TEST File has one of each manual deprecation;"""
    lint = lint_text(TEST_FILE, ['728'])
    instances = EXPECT_INSTANCES_OF_ERR.get(number, None)
    assert_contains(lint.messages, f'[U{number:03d}]', instances)


def test_check_cylc_file_7to8_has_shebang():
    """Jinja2 code comments will not be added if shebang present"""
    lint = lint_text('#!jinja2\n{{FOO}}', '', '[scheduler]')
    assert not lint.counter


def test_check_cylc_file_line_no():
    """It prints the correct line numbers"""
    lint = lint_text(TEST_FILE, ['728'])
    # the first message should be for line number 2 (line is a shebang)
    assert ':2:' in lint.messages[0]


@pytest.mark.parametrize(
    'inherit_line',
    (
        param(item, id=str(ind))
        for ind, item in enumerate([
            # lowercase family names are not permitted
            'inherit = g',
            'inherit = foo, b, a, r',
            'inherit = FOO, bar',
            'inherit = None, bar',
            'inherit = A, b, C',
            'inherit = "A", "b"',
            "inherit = 'A', 'b'",
            # parameters, jinja2 and empy should be ignored
            # but any lowercase chars before or after should not
            'inherit = a<x>z',
            'inherit = a{{ x }}z',
            'inherit = a@( x )z',
        ])
    )
)
def test_inherit_lowercase_matches(inherit_line):
    lint = lint_text(inherit_line, ['style'])
    assert any('S007' in msg for msg in lint.messages)


@pytest.mark.parametrize(
    'inherit_line',
    (
        param(item, id=str(ind))
        for ind, item in enumerate([
            # undefined values are ok
            'inherit =',
            'inherit =  ',
            # none, None and root are ok
            'inherit = none',
            'inherit = None',
            'inherit = root',
            # trailing commas and whitespace are ok
            'inherit = None,',
            'inherit = None, ',
            'inherit = None , ',
            # uppercase family names are ok
            'inherit = None, FOO, BAR',
            'inherit = FOO',
            'inherit = BAZ',
            'inherit = root',
            'inherit = FOO_BAR_0',
            # parameters should be ignored
            'inherit = A<a>Z',
            'inherit = <a=1, b-1, c+1>',
            # jinja2 should be ignored
            'inherit = A{{ a }}Z, {% for x in range(5) %}'
            'A{{ x }}, {% endfor %}',
            # empy should be ignored
            'inherit = A@( a )Z',
            # trailing comments should be ignored
            'inherit = A, B # no, comment',
            'inherit = # a',
            # quotes are ok
            'inherit = "A", "B"',
            "inherit = 'A', 'B'",
            'inherit = "None", B',
            'inherit = <a = 1, b - 1>',
            # one really awkward, but valid example
            'inherit = none, FOO_BAR_0, "<a - 1>", A<a>Z, A{{a}}Z, A@(a)Z',
        ])
    )
)
def test_inherit_lowercase_not_match_none(inherit_line):
    lint = lint_text(inherit_line, ['style'])
    assert not any('S007' in msg for msg in lint.messages)


@pytest.mark.parametrize(
    # 8 and 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(STYLE_CHECKS) + 1)) - {8, 11}
)
def test_check_cylc_file_lint(number):
    lint = lint_text(LINT_TEST_FILE, ['style'])
    assert_contains(lint.messages, f'S{number:03d}')


@pytest.mark.parametrize('code', STYLE_CHECKS.keys())
def test_check_exclusions(code):
    """It does not report any items excluded."""
    lint = lint_text(LINT_TEST_FILE, ['style'], [code])
    assert not filter_strings(lint.messages, code)


def test_check_cylc_file_jinja2_comments():
    """Jinja2 inside a Jinja2 comment should not warn"""
    lint = lint_text('#!jinja2\n{# {{ foo }} #}', ['style'])
    assert not any('S011' in msg for msg in lint.messages)


def test_check_cylc_file_jinja2_comments_shell_arithmetic_not_warned():
    """Jinja2 after a $((10#$variable)) should not warn"""
    lint = lint_text('#!jinja2\na = b$((10#$foo+5)) {{ BAR }}', ['style'])
    assert not any('S011' in msg for msg in lint.messages)


@pytest.mark.parametrize(
    # 11 won't be tested because there is no jinja2 shebang
    'number', set(range(1, len(MANUAL_DEPRECATIONS) + 1)) - {11}
)
def test_check_cylc_file_inplace(number):
    lint = lint_text(TEST_FILE, ['728', 'style'], modify=True)
    assert_contains(lint.outlines, f'[U{number:03d}]')


def test_get_cylc_files_get_all_rcs(tmp_path):
    """It returns all paths except `log/**`.
    """
    expect = [('etc', 'foo.rc'), ('bin', 'foo.rc'), ('an_other', 'foo.rc')]

    # Create a fake run directory, including the log file which should not
    # be searched:
    dirs = ['etc', 'bin', 'log', 'an_other', 'log/skarloey/']
    for path in dirs:
        thispath = tmp_path / path
        thispath.mkdir(parents=True)
        (thispath / 'foo.rc').touch()

    # Run the test
    result = [(i.parent.name, i.name) for i in get_cylc_files(tmp_path)]
    assert sorted(result) == sorted(expect)


def mock_parse_checks(*args, **kwargs):
    return {
        'U042': {
            'short': 'section `[vizualization]` has been removed.',
            'url': 'some url or other',
            'purpose': 'U',
            'rst': 'section ``[vizualization]`` has been removed.',
            'function': re.compile('not a regex')
        },
    }


def test_get_reference_rst(monkeypatch):
    """It produces a reference file for our linting."""
    monkeypatch.setattr(
        'cylc.flow.scripts.lint.parse_checks', mock_parse_checks
    )
    ref = get_reference('all', 'rst')
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        '`U042 <https://cylc.github.io/cylc-doc/stable'
        '/html/7-to-8/some url or other>`_'
        f'\n{ "^" * 78 }'
        '\nsection ``[vizualization]`` has been '
        'removed.\n\n\n'
    )
    assert ref == expect


def test_get_reference_text(monkeypatch):
    """It produces a reference file for our linting."""
    monkeypatch.setattr(
        'cylc.flow.scripts.lint.parse_checks', mock_parse_checks
    )
    ref = get_reference('all', 'text')
    expect = (
        '\n7 to 8 upgrades\n---------------\n\n'
        'U042:\n    section `[vizualization]` has been '
        'removed.'
        '\n    https://cylc.github.io/cylc-doc/stable/html/7-to-8/some'
        ' url or other\n\n\n'
    )
    assert ref == expect


@pytest.fixture()
def fixture_get_deprecations():
    """Get the deprections list for cylc.flow.cfgspec.workflow"""
    deprecations = get_upgrader_info()
    return deprecations


@pytest.mark.parametrize(
    'findme',
    [
        pytest.param(
            'abort if any task fails =',
            id='Item not available at Cylc 8'
        ),
        pytest.param(
            'timeout =',
            id='Item renamed at Cylc 8'
        ),
        pytest.param(
            '!execution retry delays',
            id='Item moved, name unchanged at Cylc 8'
        ),
        pytest.param(
            '[cylc]',
            id='Section changed at Cylc 8'
        ),
    ]
)
def test_get_upg_info(fixture_get_deprecations, findme):
    """It correctly scrapes the Cylc upgrader object.

    n.b this is just sampling to ensure that the test it getting items.
    """
    if findme.startswith('!'):
        assert not any(
            i['function'](findme) for i in fixture_get_deprecations.values()
        )
    else:
        assert any(
            i['function'](findme) for i in fixture_get_deprecations.values()
        ) is True


@pytest.mark.parametrize(
    'expect',
    [
        param({
            'rulesets': ['style'],
            'ignore': ['S004'],
            'exclude': ['sites/*.cylc']},
            id="it returns what we want"
        ),
        param({
            'northgate': ['sites/*.cylc'],
            'mons-meg': 42},
            id="it only returns requested sections"
        ),
        param({
            'max-line-length': 22},
            id='it sets max line length'
        )
    ]
)
def test_get_pyproject_toml(tmp_path, expect):
    """It returns only the lists we want from the toml file."""
    tomlcontent = "[cylc-lint]"
    permitted_keys = ['rulesets', 'ignore', 'exclude', 'max-line-length']

    for section, value in expect.items():
        tomlcontent += f'\n{section} = {value}'
    (tmp_path / 'pyproject.toml').write_text(tomlcontent)
    tomldata = get_pyproject_toml(tmp_path)

    control = {}
    for key in permitted_keys:
        control[key] = expect.get(key, [])
    assert tomldata == control


@pytest.mark.parametrize('tomlfile', [None, '', '[cylc-lint]'])
def test_get_pyproject_toml_returns_blank(tomlfile, tmp_path):
    if tomlfile is not None:
        tfile = (tmp_path / 'pyproject.toml')
        tfile.write_text(tomlfile)
    expect = {k: [] for k in {
        'exclude', 'ignore', 'max-line-length', 'rulesets'
    }}
    assert get_pyproject_toml(tmp_path) == expect


@pytest.mark.parametrize(
    'input_, error',
    [
        param(
            {'exclude': ['hey', 'there', 'Delilah']},
            None,
            id='it works'
        ),
        param(
            {'foo': ['hey', 'there', 'Delilah', 42]},
            'allowed',
            id='it fails with illegal section name'
        ),
        param(
            {'exclude': 'woo!'},
            'should be a list, but',
            id='it fails with illegal section type'
        ),
        param(
            {'exclude': ['hey', 'there', 'Delilah', 42]},
            'should be a string',
            id='it fails with illegal value name'
        ),
        param(
            {'rulesets': ['hey']},
            'hey not valid: Rulesets can be',
            id='it fails with illegal ruleset'
        ),
        param(
            {'ignore': ['hey']},
            'hey not valid: Ignore codes',
            id='it fails with illegal ignores'
        ),
        param(
            {'ignore': ['R999']},
            'R999 is a not a known linter code.',
            id='it fails with non-existant checks ignored'
        )
    ]
)
def test_validate_toml_items(input_, error):
    """It chucks out the wrong sort of items."""
    if error is not None:
        with pytest.raises(CylcError, match=error):
            validate_toml_items(input_)
    else:
        assert validate_toml_items(input_) is True


@pytest.mark.parametrize(
    'clidata, tomldata, expect',
    [
        param(
            {
                'rulesets': ['foo', 'bar'],
                'ignore': ['R101'],
            },
            {
                'rulesets': ['baz'],
                'ignore': ['R100'],
                'exclude': ['not_me-*.cylc']
            },
            {
                'rulesets': ['foo', 'bar'],
                'ignore': ['R100', 'R101'],
                'exclude': ['not_me-*.cylc'],
                'max-line-length': None
            },
            id='It works with good path'
        ),
    ]
)
def test_merge_cli_with_tomldata(clidata, tomldata, expect):
    """It merges each of the three sections correctly: see function.__doc__"""
    assert _merge_cli_with_tomldata(clidata, tomldata) == expect


def test_invalid_tomlfile(tmp_path):
    """It fails nicely if pyproject.toml is malformed"""
    tomlfile = (tmp_path / 'pyproject.toml')
    tomlfile.write_text('foo :{}')
    expected_msg = 'pyproject.toml did not load:'
    with pytest.raises(CylcError, match=expected_msg):
        get_pyproject_toml(tmp_path)


@pytest.mark.parametrize(
    'ref, expect',
    [
        [True, 'line > ``<max_line_len>`` characters'],
        [False, 'line > 42 characters']
    ]
)
def test_parse_checks_reference_mode(ref, expect):
    """Add extra explanation of max line legth setting in reference mode.
    """
    result = parse_checks(['style'], reference=ref, max_line_len=42)
    value = result['S012']
    assert expect in value['short']


@pytest.mark.parametrize(
    'spaces, expect',
    (
        (0, 'S002'),
        (1, 'S013'),
        (2, 'S013'),
        (3, 'S013'),
        (4, None),
        (5, 'S013'),
        (6, 'S013'),
        (7, 'S013'),
        (8, None),
        (9, 'S013')
    )
)
def test_indents(spaces, expect):
    """Test different wrong indentations

    Parameterization deliberately over-obvious to avoid replicating
    arithmetic logic from code. Dangerously close to re-testing ``%``
    builtin.
    """
    result = lint_text(
        f"{' ' * spaces}foo = 42",
        ['style']
    )
    result = ''.join(result.messages)
    if expect:
        assert expect in result
    else:
        assert not result
